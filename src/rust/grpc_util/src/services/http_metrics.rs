// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::task::{Context, Poll};
use std::time::Instant;

use hyper::body::HttpBody;
use hyper::{Request, Response};
use metrics::{histogram, increment_counter};
use tonic::body::BoxBody;
use tower::Service;

/// A `tower::Service` that generates HTTP-level metrics.
pub struct HttpMetrics<S> {
    inner: S,
}

impl<S> HttpMetrics<S> {
    #[allow(dead_code)]
    pub fn new(inner: S) -> Self {
        HttpMetrics { inner }
    }
}

impl<S, B> Service<Request<B>> for HttpMetrics<S>
where
    S: Service<Request<B>, Response = Response<BoxBody>> + Clone + Send + 'static,
    S::Future: Send + 'static,
    B: HttpBody + Send + 'static,
{
    type Response = S::Response;
    type Error = S::Error;
    type Future = futures::future::BoxFuture<'static, Result<Self::Response, Self::Error>>;

    fn poll_ready(&mut self, cx: &mut Context<'_>) -> Poll<Result<(), Self::Error>> {
        self.inner.poll_ready(cx)
    }

    fn call(&mut self, request: Request<B>) -> Self::Future {
        let mut svc = self.inner.clone();

        Box::pin(async move {
            let method = request.method().as_str().to_owned();

            increment_counter!("http_server_requests_started_total", "method" => method.clone());

            let start_time = Instant::now();
            let response = svc.call(request).await; // should be no errors at this point
            let elapsed = start_time.elapsed();

            histogram!("http_server_requests_handling_seconds", elapsed, "method" => method.clone());

            let status = response
                .as_ref()
                .map(|r| r.status().as_u16().to_string())
                .unwrap_or_else(|_| "N/A".to_owned());

            increment_counter!(
                "http_server_requests_handled_total",
                "method" => method,
                "status" => status,
            );

            response
        })
    }
}
