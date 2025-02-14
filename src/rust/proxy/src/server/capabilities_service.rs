// Copyright 2020 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::sync::Arc;

use grpc_util::auth::{AuthScheme, Permissions};
use protos::build::bazel::remote::execution::v2::{
    capabilities_server::Capabilities, GetCapabilitiesRequest, ServerCapabilities,
};
use tonic::{Request, Response, Status};

use crate::server::{client_call, ProxyServerInner};

pub(crate) struct CapabilitiesService {
    inner: Arc<ProxyServerInner>,
    auth_scheme: AuthScheme,
}

impl CapabilitiesService {
    pub const SERVICE_NAME: &'static str = "build.bazel.remote.execution.v2.Capabilities";

    pub(crate) fn new(inner: Arc<ProxyServerInner>, auth_scheme: AuthScheme) -> Self {
        CapabilitiesService { inner, auth_scheme }
    }
}

#[tonic::async_trait]
impl Capabilities for CapabilitiesService {
    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn get_capabilities(
        &self,
        request: Request<GetCapabilitiesRequest>,
    ) -> Result<Response<ServerCapabilities>, Status> {
        let requested_instance_name = &request.get_ref().instance_name;
        self.inner.check_authorized(
            self.auth_scheme,
            request.metadata(),
            requested_instance_name,
            Permissions::Read,
        )?;

        // TODO: Merge in execution capabilities call as well if configured.
        let client = self
            .inner
            .backend(requested_instance_name)
            .cas_capabilities
            .clone();
        let request = request.into_inner();
        client_call(
            client,
            move |mut client| {
                let request = request.clone();
                async move { client.get_capabilities(request).await }
            },
            Self::SERVICE_NAME,
            "GetCapabilities",
        )
        .await
    }
}
