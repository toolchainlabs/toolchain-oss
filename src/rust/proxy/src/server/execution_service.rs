// Copyright 2020 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::sync::Arc;

use ginepro::LoadBalancedChannel;
use grpc_util::auth::{AuthScheme, Permissions};
use protos::build::bazel::remote::execution::v2::{
    execution_client::ExecutionClient, execution_server::Execution, ExecuteRequest,
    WaitExecutionRequest,
};
use protos::google::longrunning::Operation;
use tonic::metadata::MetadataMap;
use tonic::{Request, Response, Status};

use execution_util::instance_name_from_session_name;

use crate::server::{client_call, ProxyServerInner};

pub(crate) struct ExecutionService {
    inner: Arc<ProxyServerInner>,
    auth_scheme: AuthScheme,
}

impl ExecutionService {
    pub const SERVICE_NAME: &'static str = "build.bazel.remote.execution.v2.Execution";

    pub(crate) fn new(inner: Arc<ProxyServerInner>, auth_scheme: AuthScheme) -> Self {
        ExecutionService { inner, auth_scheme }
    }

    fn get_client(
        &self,
        metadata: &MetadataMap,
        requested_instance_name: &str,
    ) -> Result<ExecutionClient<LoadBalancedChannel>, Status> {
        self.inner.check_authorized(
            self.auth_scheme,
            metadata,
            requested_instance_name,
            Permissions::Execute,
        )?;
        self.inner
            .backend(requested_instance_name)
            .execution
            .as_ref()
            .cloned()
            .ok_or_else(|| {
                Status::invalid_argument(format!("No such instance: {requested_instance_name}"))
            })
    }
}

#[tonic::async_trait]
impl Execution for ExecutionService {
    type ExecuteStream = tonic::codec::Streaming<Operation>;

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn execute(
        &self,
        request: Request<ExecuteRequest>,
    ) -> Result<Response<Self::ExecuteStream>, Status> {
        let instance_name = &request.get_ref().instance_name;
        let client = self.get_client(request.metadata(), instance_name)?;
        let request = request.into_inner();
        client_call(
            client,
            move |mut client| {
                let request = request.clone();
                async move { client.execute(request).await }
            },
            Self::SERVICE_NAME,
            "Execute",
        )
        .await
    }

    type WaitExecutionStream = tonic::codec::Streaming<Operation>;

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn wait_execution(
        &self,
        request: Request<WaitExecutionRequest>,
    ) -> Result<Response<Self::WaitExecutionStream>, Status> {
        let instance_name = instance_name_from_session_name(&request.get_ref().name)
            .map_err(Status::invalid_argument)?;

        let client = self.get_client(request.metadata(), &instance_name)?;
        let request = request.into_inner();
        client_call(
            client,
            move |mut client| {
                let request = request.clone();
                async move { client.wait_execution(request).await }
            },
            Self::SERVICE_NAME,
            "WaitExecution",
        )
        .await
    }
}
