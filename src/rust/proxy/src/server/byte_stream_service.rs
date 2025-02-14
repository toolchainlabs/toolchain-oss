// Copyright 2020 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use futures::StreamExt;
use ginepro::LoadBalancedChannel;
use grpc_util::auth::{AuthScheme, Permissions};
use protos::google::bytestream::{
    byte_stream_client::ByteStreamClient, byte_stream_server::ByteStream, QueryWriteStatusRequest,
    QueryWriteStatusResponse, ReadRequest, ReadResponse, WriteRequest, WriteResponse,
};
use tokio::sync::Mutex;
use tonic::metadata::MetadataMap;
use tonic::{Request, Response, Status, Streaming};

use crate::server::{client_call, ProxyServerInner};

pub(crate) struct ByteStreamService {
    inner: Arc<ProxyServerInner>,
    auth_scheme: AuthScheme,
}

impl ByteStreamService {
    pub const SERVICE_NAME: &'static str = "google.bytestream.ByteStream";

    pub(crate) fn new(inner: Arc<ProxyServerInner>, auth_scheme: AuthScheme) -> Self {
        ByteStreamService { inner, auth_scheme }
    }

    fn get_client(
        &self,
        metadata: &MetadataMap,
        resource_name: &str,
        required_permissions: Permissions,
    ) -> Result<ByteStreamClient<LoadBalancedChannel>, Status> {
        let parts = resource_name.split('/').collect::<Vec<_>>();
        let instance_name = match parts.first() {
            Some(&n) => n,
            None => return Err(Status::invalid_argument("unable to parse instance name")),
        };

        self.inner.check_authorized(
            self.auth_scheme,
            metadata,
            instance_name,
            required_permissions,
        )?;
        Ok(self.inner.backend(instance_name).bytestream.clone())
    }
}

#[tonic::async_trait]
impl ByteStream for ByteStreamService {
    type ReadStream = tonic::codec::Streaming<ReadResponse>;

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn read(
        &self,
        request: Request<ReadRequest>,
    ) -> Result<Response<Self::ReadStream>, Status> {
        let mut client = self.get_client(
            request.metadata(),
            &request.get_ref().resource_name,
            Permissions::Read,
        )?;
        client.read(request).await
    }

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn write(
        &self,
        request: Request<Streaming<WriteRequest>>,
    ) -> Result<Response<WriteResponse>, Status> {
        // Retrieve the first message from the stream to identify the requested backend instance
        // from the resource name.
        let outer_req_metadata = request.metadata().clone();
        let stream = Arc::new(Mutex::new(request.into_inner()));
        let first_msg = stream
            .lock()
            .await
            .next()
            .await
            .unwrap_or_else(|| Err(Status::aborted("connection closed")))?;
        let client = self.get_client(
            &outer_req_metadata,
            &first_msg.resource_name,
            Permissions::ReadWrite,
        )?;

        // A place for the closure to store whether it had taken any elements off the stream
        // from the ultimate client. If it does, then it cannot retry as the proxy has no
        // way to replay the stream.
        let already_saw_messages = Arc::new(AtomicBool::new(false));

        // Create a future to receive the final result from the backend.
        client_call(
            client,
            move |mut client| {
                let first_msg = first_msg.clone();
                let stream = stream.clone();
                let already_saw_messages = already_saw_messages.clone();
                async move {
                    if already_saw_messages.load(Ordering::SeqCst) {
                        return Err(Status::aborted(
                            "Request aborted due to backend error; please retry request",
                        ));
                    }

                    let write_error: Arc<Mutex<Option<Result<Response<WriteResponse>, Status>>>> =
                        Arc::new(Mutex::new(None));

                    let response = client
                        .write(Request::new({
                            let write_error = write_error.clone();
                            async_stream::stream! {
                              // Send the first message that was already retrieved to the backend.
                              yield first_msg;

                              // Loop over the remaining messages in the client's stream and relay those messages
                              // to the backend.
                              while let Some(write_request_res) = stream.lock().await.next().await {
                                  already_saw_messages.store(true, Ordering::SeqCst);
                                  match write_request_res {
                                    Ok(write_request) => yield write_request,
                                    Err(e) => {
                                        *write_error.lock().await = Some(Err(e));
                                        break;
                                    }
                                  }
                              }
                            }
                        }))
                        .await;

                    let write_error = write_error.lock().await.take();
                    write_error.unwrap_or(response)
                }
            },
            Self::SERVICE_NAME,
            "Write",
        )
        .await
    }

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn query_write_status(
        &self,
        request: Request<QueryWriteStatusRequest>,
    ) -> Result<Response<QueryWriteStatusResponse>, Status> {
        let client = self.get_client(
            request.metadata(),
            &request.get_ref().resource_name,
            Permissions::ReadWrite,
        )?;
        let request = request.into_inner();
        client_call(
            client,
            move |mut client| {
                let request = request.clone();
                async move { client.query_write_status(request).await }
            },
            Self::SERVICE_NAME,
            "QueryWriteStatus",
        )
        .await
    }
}
