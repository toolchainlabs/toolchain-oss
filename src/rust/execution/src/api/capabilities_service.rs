// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use protos::build::bazel::remote::execution::v2::{
    capabilities_server::Capabilities, GetCapabilitiesRequest, ServerCapabilities,
};
use tonic::{Request, Response, Status};

use crate::api::ExecutionServer;

#[tonic::async_trait]
impl Capabilities for ExecutionServer {
    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn get_capabilities(
        &self,
        _request: Request<GetCapabilitiesRequest>,
    ) -> Result<Response<ServerCapabilities>, Status> {
        Ok(Response::new(ServerCapabilities::default()))
    }
}
