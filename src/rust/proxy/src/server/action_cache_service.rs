// Copyright 2020 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::sync::Arc;

use ginepro::LoadBalancedChannel;
use grpc_util::auth::{AuthScheme, Permissions};
use protos::build::bazel::remote::execution::v2::{
    action_cache_client::ActionCacheClient, action_cache_server::ActionCache, ActionResult,
    GetActionResultRequest, UpdateActionResultRequest,
};
use tonic::metadata::MetadataMap;
use tonic::{Request, Response, Status};

use crate::server::{client_call, ProxyServerInner};

#[allow(clippy::result_large_err)]

pub(crate) struct ActionCacheService {
    inner: Arc<ProxyServerInner>,
    auth_scheme: AuthScheme,
}

impl ActionCacheService {
    pub const SERVICE_NAME: &'static str = "build.bazel.remote.execution.v2.ActionCache";

    pub(crate) fn new(inner: Arc<ProxyServerInner>, auth_scheme: AuthScheme) -> Self {
        ActionCacheService { inner, auth_scheme }
    }

    fn get_client(
        &self,
        metadata: &MetadataMap,
        requested_instance_name: &str,
        required_permissions: Permissions,
    ) -> Result<ActionCacheClient<LoadBalancedChannel>, Status> {
        self.inner.check_authorized(
            self.auth_scheme,
            metadata,
            requested_instance_name,
            required_permissions,
        )?;
        Ok(self
            .inner
            .backend(requested_instance_name)
            .action_cache
            .clone())
    }
}

#[tonic::async_trait]
impl ActionCache for ActionCacheService {
    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn get_action_result(
        &self,
        request: Request<GetActionResultRequest>,
    ) -> Result<Response<ActionResult>, Status> {
        let client = self.get_client(
            request.metadata(),
            &request.get_ref().instance_name,
            Permissions::Read,
        )?;
        let request = request.into_inner();
        client_call(
            client,
            move |mut client| {
                let request = request.clone();
                async move {
                    let response_fut = client.get_action_result(request);
                    match self.inner.timeouts.get_action_result {
                        Some(d) => {
                            tokio::time::timeout(d, response_fut)
                                .await
                                .unwrap_or_else(|_| {
                                    metrics::counter!(
                                        "toolchain_proxy_backend_requests_timed_out_total",
                                        1,
                                        "grpc_service" => Self::SERVICE_NAME.to_owned(),
                                        "grpc_method" => "GetActionResult".to_owned(),
                                    );
                                    Err(Status::unavailable("storage backend timeout"))
                                })
                        }
                        None => response_fut.await,
                    }
                }
            },
            Self::SERVICE_NAME,
            "GetActionResult",
        )
        .await
    }

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn update_action_result(
        &self,
        request: Request<UpdateActionResultRequest>,
    ) -> Result<Response<ActionResult>, Status> {
        let client = self.get_client(
            request.metadata(),
            &request.get_ref().instance_name,
            Permissions::ReadWrite,
        )?;
        let request = request.into_inner();
        client_call(
            client,
            move |mut client| {
                let request = request.clone();
                async move { client.update_action_result(request).await }
            },
            Self::SERVICE_NAME,
            "UpdateActionResult",
        )
        .await
    }
}
