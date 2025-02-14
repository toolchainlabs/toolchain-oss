// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::borrow::Cow;
use std::pin::Pin;
use std::task::{Context, Poll};
use std::time::{Duration, Instant};

use http_body::SizeHint;
use hyper::body::HttpBody;
use hyper::header::HeaderValue;
use hyper::{Body, HeaderMap, Request as HyperRequest, Response as HyperResponse};
use metrics::{histogram, increment_counter};
use percent_encoding::percent_decode;
use pin_project::{pin_project, pinned_drop};
use tonic::{body::BoxBody, transport::NamedService, Status};
use tower::{Service, ServiceExt};

const GRPC_STATUS_HEADER_CODE: &str = "grpc-status";
const GRPC_STATUS_MESSAGE_HEADER: &str = "grpc-message";

/// Callbacks for RPC events.
pub trait GrpcMetricReporter {
    /// Called at the start of an RPC.
    fn report_rpc_start(&self, service_name: &'static str, service_method: String);

    /// Called upon completion of an RPC.
    fn report_rpc_complete(
        &self,
        service_name: &'static str,
        service_method: String,
        code: &'static str,
        elapsed: Duration,
    );
}

/// Logs RPC start and end as time-series metrics. The counters are named after
/// the equivalent counters in
/// https://github.com/grpc-ecosystem/go-grpc-prometheus/blob/master/server_metrics.go.
#[derive(Clone, Default)]
pub struct DefaultGrpcMetricsReporter;

impl GrpcMetricReporter for DefaultGrpcMetricsReporter {
    fn report_rpc_start(&self, service_name: &'static str, service_method: String) {
        increment_counter!(
            "grpc_server_started_total",
            "grpc_service" => service_name,
            "grpc_method" => service_method,
        );
    }

    fn report_rpc_complete(
        &self,
        service_name: &'static str,
        service_method: String,
        code: &'static str,
        elapsed: Duration,
    ) {
        histogram!(
            "grpc_server_handling_seconds",
            elapsed,
            "grpc_service" => service_name,
            "grpc_method" => service_method.clone(),
        );

        // Record that the RPC call completed.
        increment_counter!(
            "grpc_server_handled_total",
            "grpc_service" => service_name,
            "grpc_method" => service_method,
            "grpc_code" => code,
        );
    }
}

/// A `tower::Service` that reports the start and end of RPCs passing through it to an
/// underlying gRPC service. An associated "reporter" receives the events.
#[derive(Debug, Clone)]
pub struct GrpcMetrics<S, R> {
    inner: S,
    reporter: R,
}

impl<S> GrpcMetrics<S, DefaultGrpcMetricsReporter> {
    pub fn new(service: S) -> Self {
        Self::with_reporter(service, DefaultGrpcMetricsReporter)
    }
}

impl<S, R> GrpcMetrics<S, R> {
    pub fn with_reporter(service: S, reporter: R) -> Self {
        GrpcMetrics {
            inner: service,
            reporter,
        }
    }

    ///
    /// Returns the message to use if the given code and message should be reported to Sentry.
    /// See https://grpc.github.io/grpc/core/md_doc_statuscodes.html.
    ///
    fn report_to_sentry<'h>(code: &str, message: Option<&'h HeaderValue>) -> Option<Cow<'h, str>> {
        match code {
            "OK" | "Aborted" | "DeadlineExceeded" | "NotFound" | "AlreadyExists"
            | "PermissionDenied" | "FailedPrecondition" | "OutOfRange" | "Unauthenticated"
            | "Canceled" | "Unavailable" => return None,
            _ => {
                // Fall through to decode.
            }
        };
        let message_value = message.map(|m| percent_decode(m.as_bytes()).decode_utf8_lossy());
        // We explicitly list codes that we're aware of, in addition to the wildcard.
        #[allow(clippy::wildcard_in_or_patterns)]
        match code {
            "Internal" | "Unknown" => {
                // Report the error only if the message does not contain some known-useless
                // messages.
                message_value
                    .filter(|m| {
                        // TODO: See https://github.com/toolchainlabs/toolchain/issues/10407.
                        m.contains("protocol error: unexpected internal error encountered")
                    })
                    .filter(|m| {
                        // TODO: See https://github.com/toolchainlabs/toolchain/issues/10408.
                        m.contains("Unexpected EOF decoding stream.")
                    })
                    .filter(|m| {
                        // TODO: See https://github.com/toolchainlabs/toolchain/issues/10409.
                        m.contains("transport error")
                    })
                    .filter(|m| {
                        // A type of cancellation. Ignore.
                        m.contains("stream no longer needed")
                    })
                    .filter(|m| m.contains("protocol error: unexpected internal error encountered"))
            }
            "InvalidArgument" | "ResourceExhausted" | "Unimplemented" | "DataLoss" | _ => {
                // Unexpected: report, even if we don't have a message.
                message_value.or_else(|| Some("".into()))
            }
        }
    }
}

impl<S, R> Service<HyperRequest<Body>> for GrpcMetrics<S, R>
where
    S: Service<HyperRequest<Body>, Response = HyperResponse<BoxBody>>
        + NamedService
        + Clone
        + Send
        + 'static,
    S::Future: Send + 'static,
    R: GrpcMetricReporter + Send + Sync + Clone + 'static,
{
    type Response = S::Response;
    type Error = S::Error;
    type Future = futures::future::BoxFuture<'static, Result<Self::Response, Self::Error>>;

    fn poll_ready(&mut self, cx: &mut Context<'_>) -> Poll<Result<(), Self::Error>> {
        self.inner.poll_ready(cx)
    }

    fn call(&mut self, request: HyperRequest<Body>) -> Self::Future {
        let svc = self.inner.clone();
        let reporter = self.reporter.clone();

        Box::pin(async move {
            // Parse out the service and method names. Ignore any other path not of the
            // expected form so we do not log gRPC metrics for search engine bots etc.
            let service_method = match request
                .uri()
                .path()
                .split('/')
                .collect::<Vec<_>>()
                .as_slice()
            {
                ["", service, method] if *service == <S as NamedService>::NAME => {
                    (*method).to_owned()
                }
                _ => {
                    log::error!("grpc_metrics: unable to decode URI: {:?}", request.uri());
                    let mut response = HyperResponse::new(tonic::body::empty_body());
                    *response.status_mut() = hyper::StatusCode::INTERNAL_SERVER_ERROR;
                    return Ok(response);
                }
            };

            // Report that the RPC call started.
            reporter.report_rpc_start(<S as NamedService>::NAME, service_method.clone());

            let start_time = Instant::now();

            let service_method2 = service_method.clone();
            let reporter2 = reporter.clone();
            let mut svc = svc.map_response(move |r| {
                let (parts, body) = r.into_parts();
                HyperResponse::from_parts(
                    parts,
                    BoxBody::new(OutboundBody::new(
                        body,
                        <S as NamedService>::NAME,
                        service_method2,
                        start_time,
                        reporter2,
                    )),
                )
            });

            // Call the underlying service.
            let response = match svc.call(request).await {
                Ok(response) => {
                    if let Some(hv) = response.headers().get(GRPC_STATUS_HEADER_CODE) {
                        let code = parse_status_code(hv);
                        let message = response.headers().get(GRPC_STATUS_MESSAGE_HEADER);
                        let call_duration = start_time.elapsed();
                        reporter.report_rpc_complete(
                            <S as NamedService>::NAME,
                            service_method.clone(),
                            code,
                            call_duration,
                        );

                        if let Some(grpc_message) = Self::report_to_sentry(code, message) {
                            use sentry::protocol::{Event, Level};
                            use sentry::types::Uuid;

                            let event = Event {
                                event_id: Uuid::new_v4(),
                                level: Level::Error,
                                message: Some(format!(
                                    "{}/{}: {}: {}",
                                    <S as NamedService>::NAME,
                                    service_method,
                                    code,
                                    grpc_message
                                )),
                                ..Event::default()
                            };

                            sentry::capture_event(event);
                        }
                    }
                    response
                }
                Err(_) => {
                    log::debug!("illegal state - service should have only returned a response");
                    let mut response = HyperResponse::new(tonic::body::empty_body());
                    *response.status_mut() = hyper::StatusCode::INTERNAL_SERVER_ERROR;

                    let call_duration = start_time.elapsed();
                    reporter.report_rpc_complete(
                        <S as NamedService>::NAME,
                        service_method.clone(),
                        "Internal",
                        call_duration,
                    );

                    return Ok(response);
                }
            };

            Ok(response)
        })
    }
}

impl<S: NamedService, R> NamedService for GrpcMetrics<S, R> {
    const NAME: &'static str = S::NAME;
}

/// Wraps the response BoxBody so that GrpcMetrics may monitor for completion.
#[pin_project(PinnedDrop)]
struct OutboundBody<R: GrpcMetricReporter> {
    #[pin]
    inner: BoxBody,
    service_name: &'static str,
    service_method: String,
    start_time: Instant,
    status: Option<Status>,
    reporter: R,
    complete: bool,
}

impl<R: GrpcMetricReporter> OutboundBody<R> {
    pub fn new(
        inner: BoxBody,
        service_name: &'static str,
        service_method: String,
        start_time: Instant,
        reporter: R,
    ) -> Self {
        OutboundBody {
            inner,
            service_name,
            service_method,
            start_time,
            status: None,
            reporter,
            complete: false,
        }
    }
}

impl<R> HttpBody for OutboundBody<R>
where
    R: GrpcMetricReporter + Clone,
{
    type Data = <BoxBody as HttpBody>::Data;
    type Error = <BoxBody as HttpBody>::Error;

    fn is_end_stream(&self) -> bool {
        self.inner.is_end_stream()
    }

    fn size_hint(&self) -> SizeHint {
        self.inner.size_hint()
    }

    fn poll_data(
        self: Pin<&mut Self>,
        cx: &mut Context<'_>,
    ) -> Poll<Option<Result<Self::Data, Self::Error>>> {
        let this = self.project();
        this.inner.poll_data(cx)
    }

    fn poll_trailers(
        self: Pin<&mut Self>,
        cx: &mut Context<'_>,
    ) -> Poll<Result<Option<HeaderMap<HeaderValue>>, Self::Error>> {
        let this = self.project();

        let trailers_opt = match futures::ready!(this.inner.poll_trailers(cx)) {
            Ok(t) => t,
            Err(err) => return Poll::Ready(Err(err)),
        };

        let code_opt = trailers_opt
            .as_ref()
            .and_then(|t| t.get(GRPC_STATUS_HEADER_CODE))
            .map(parse_status_code);
        if let Some(code) = code_opt {
            // Record the duration of the underlying service call.
            let call_duration = this.start_time.elapsed();
            *this.complete = true;
            this.reporter.report_rpc_complete(
                this.service_name,
                (*this.service_method).clone(),
                code,
                call_duration,
            );
        }

        Poll::Ready(Ok(trailers_opt))
    }
}

#[pinned_drop]
impl<R: GrpcMetricReporter> PinnedDrop for OutboundBody<R> {
    fn drop(self: Pin<&mut Self>) {
        if !self.complete {
            let call_duration = self.start_time.elapsed();
            self.reporter.report_rpc_complete(
                self.service_name,
                self.service_method.clone(),
                "Canceled",
                call_duration,
            );
        }
    }
}

pub fn convert_status_code(code: u16) -> &'static str {
    match code {
        0 => "OK",
        1 => "Canceled",
        2 => "Unknown",
        3 => "InvalidArgument",
        4 => "DeadlineExceeded",
        5 => "NotFound",
        6 => "AlreadyExists",
        7 => "PermissionDenied",
        8 => "ResourceExhausted",
        9 => "FailedPrecondition",
        10 => "Aborted",
        11 => "OutOfRange",
        12 => "Unimplemented",
        13 => "Internal",
        14 => "Unavailable",
        15 => "DataLoss",
        16 => "Unauthenticated",
        _ => "--INVALID--",
    }
}

/// Parse the gRPC status from headers.
/// Note: This should be replaced with the Tonic version once it is made public:
/// https://github.com/hyperium/tonic/blob/61555ff2b5b76e4e3172717354aed1e6f31d6611/tonic/src/status.rs#L383.
fn parse_status_code(value: &HeaderValue) -> &'static str {
    let value_as_str: Result<&str, _> = value.to_str().map_err(|_| "--INVALID--");
    value_as_str
        .and_then(|x| {
            x.parse::<u16>()
                .map(convert_status_code)
                .map_err(|_| "--INVALID--")
        })
        .unwrap_or("--INVALID--")
}

#[cfg(test)]
mod tests {
    use std::mem;
    use std::sync::Arc;

    use bytes::{BufMut, BytesMut};
    use http_body::Body as HttpBody;
    use hyper::body::Body;
    use hyper::header::HeaderValue;
    use hyper::Request as HyperRequest;
    use hyper::{Method, StatusCode, Uri};
    use parking_lot::Mutex;
    use prost::Message;
    use protos::build::bazel::remote::execution::v2::{
        content_addressable_storage_server::{
            ContentAddressableStorage, ContentAddressableStorageServer,
        },
        BatchReadBlobsRequest, BatchReadBlobsResponse, BatchUpdateBlobsRequest,
        BatchUpdateBlobsResponse, FindMissingBlobsRequest, FindMissingBlobsResponse,
        GetTreeRequest, GetTreeResponse,
    };
    use tonic::{Request, Response, Status};
    use tower::Service;

    use super::{parse_status_code, GrpcMetrics};
    use crate::services::grpc_metrics::GrpcMetricReporter;
    use std::time::Duration;

    #[derive(Clone)]
    struct MockCapabilities;

    #[tonic::async_trait]
    impl ContentAddressableStorage for MockCapabilities {
        async fn find_missing_blobs(
            &self,
            _request: Request<FindMissingBlobsRequest>,
        ) -> Result<Response<FindMissingBlobsResponse>, Status> {
            Ok(Response::new(FindMissingBlobsResponse {
                missing_blob_digests: Vec::new(),
            }))
        }

        async fn batch_update_blobs(
            &self,
            _request: Request<BatchUpdateBlobsRequest>,
        ) -> Result<Response<BatchUpdateBlobsResponse>, Status> {
            Err(Status::unimplemented("batch_update_blobs"))
        }

        async fn batch_read_blobs(
            &self,
            _request: Request<BatchReadBlobsRequest>,
        ) -> Result<Response<BatchReadBlobsResponse>, Status> {
            Err(Status::unimplemented("batch_read_blobs"))
        }

        type GetTreeStream = tonic::codec::Streaming<GetTreeResponse>;

        async fn get_tree(
            &self,
            _request: Request<GetTreeRequest>,
        ) -> Result<Response<Self::GetTreeStream>, Status> {
            Err(Status::unimplemented("get_tree"))
        }
    }

    #[derive(Clone)]
    struct TestGrpcMetricsReporter {
        starts: Arc<Mutex<Vec<String>>>,
        completions: Arc<Mutex<Vec<String>>>,
    }

    impl TestGrpcMetricsReporter {
        pub fn new() -> Self {
            TestGrpcMetricsReporter {
                starts: Arc::new(Mutex::new(Vec::new())),
                completions: Arc::new(Mutex::new(Vec::new())),
            }
        }
    }

    impl GrpcMetricReporter for TestGrpcMetricsReporter {
        fn report_rpc_start(&self, service_name: &'static str, service_method: String) {
            let mut starts = self.starts.lock();
            starts.push(format!("{service_name}-{service_method}"));
        }

        fn report_rpc_complete(
            &self,
            service_name: &'static str,
            service_method: String,
            code: &'static str,
            _elapsed: Duration,
        ) {
            let mut completions = self.completions.lock();
            completions.push(format!("{service_name}-{service_method}-{code}"));
        }
    }

    #[tokio::test]
    async fn collects_grpc_metrics_successfully() {
        let reporter = TestGrpcMetricsReporter::new();
        let mut service = GrpcMetrics::with_reporter(
            ContentAddressableStorageServer::new(MockCapabilities),
            reporter.clone(),
        );

        // First make a request that is known to succeed.
        let request = FindMissingBlobsRequest {
            instance_name: "main".to_owned(),
            blob_digests: Vec::new(),
        };
        let request_bytes = {
            let mut buf = BytesMut::with_capacity(
                mem::size_of::<u8>() + mem::size_of::<u32>() + request.encoded_len(),
            );
            buf.put_u8(0); // flags - no compression
            buf.put_u32(request.encoded_len() as u32); // size of message
            request.encode(&mut buf).unwrap();
            buf.freeze()
        };
        let mut request = HyperRequest::new(Body::from(request_bytes));
        *request.method_mut() = Method::GET;
        *request.uri_mut() = Uri::from_static(
            "http://example.com/build.bazel.remote.execution.v2.ContentAddressableStorage/FindMissingBlobs",
        );

        // Make the RPC call and drive the body to completion by awaiting data and trailers.
        let response = service.call(request).await.unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        let mut body = response.into_body();
        while let Some(_) = body.data().await {}
        let _ = body.trailers().await;

        // The test reporter should have received events for the RPC call.
        {
            let starts = reporter.starts.lock();
            assert_eq!(
                *starts,
                vec![
                    "build.bazel.remote.execution.v2.ContentAddressableStorage-FindMissingBlobs"
                        .to_owned()
                ]
            );
        }
        {
            let completions = reporter.completions.lock();
            assert_eq!(
                *completions,
                vec![
                    "build.bazel.remote.execution.v2.ContentAddressableStorage-FindMissingBlobs-OK"
                        .to_owned()
                ]
            );
        }

        // Now make an RPC call that will fail.
        let request = BatchReadBlobsRequest {
            instance_name: "main".to_owned(),
            digests: Vec::new(),
        };
        let request_bytes = {
            let mut buf = BytesMut::with_capacity(
                mem::size_of::<u8>() + mem::size_of::<u32>() + request.encoded_len(),
            );
            buf.put_u8(0); // flags - no compression
            buf.put_u32(request.encoded_len() as u32); // size of message
            request.encode(&mut buf).unwrap();
            buf.freeze()
        };
        let mut request = HyperRequest::new(Body::from(request_bytes));
        *request.method_mut() = Method::GET;
        *request.uri_mut() = Uri::from_static(
            "http://example.com/build.bazel.remote.execution.v2.ContentAddressableStorage/BatchReadBlobs",
        );

        // Make the RPC call and drive the body to completion by awaiting data and trailers.
        let response = service.call(request).await.unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        let mut body = response.into_body();
        while let Some(_) = body.data().await {}
        let _ = body.trailers().await;

        // The test reporter should have received events for the first RPC call and also
        // this RPC call.
        {
            let starts = reporter.starts.lock();
            assert_eq!(
                *starts,
                vec![
                    "build.bazel.remote.execution.v2.ContentAddressableStorage-FindMissingBlobs"
                        .to_owned(),
                    "build.bazel.remote.execution.v2.ContentAddressableStorage-BatchReadBlobs"
                        .to_owned(),
                ]
            );
        }
        {
            let completions = reporter.completions.lock();
            assert_eq!(
                *completions,
                vec![
                    "build.bazel.remote.execution.v2.ContentAddressableStorage-FindMissingBlobs-OK"
                        .to_owned(),
                    "build.bazel.remote.execution.v2.ContentAddressableStorage-BatchReadBlobs-Unimplemented"
                        .to_owned(),
                ]
            );
        }
    }

    #[test]
    fn parses_status_from_headers_successfully() {
        let status_table = vec![
            (0, "OK"),
            (1, "Canceled"),
            (2, "Unknown"),
            (3, "InvalidArgument"),
            (4, "DeadlineExceeded"),
            (5, "NotFound"),
            (6, "AlreadyExists"),
            (7, "PermissionDenied"),
            (8, "ResourceExhausted"),
            (9, "FailedPrecondition"),
            (10, "Aborted"),
            (11, "OutOfRange"),
            (12, "Unimplemented"),
            (13, "Internal"),
            (14, "Unavailable"),
            (15, "DataLoss"),
            (16, "Unauthenticated"),
        ];

        for (code, expected_msg) in status_table {
            let actual_msg = parse_status_code(&HeaderValue::from(code));
            assert_eq!(expected_msg, actual_msg);
        }
    }

    #[test]
    fn handles_invalid_status() {
        let status_table = ["17", "-1", "xyzzy"];

        for status in &status_table {
            let actual_msg = parse_status_code(&HeaderValue::from_static(status));
            assert_eq!("--INVALID--", actual_msg);
        }
    }
}
