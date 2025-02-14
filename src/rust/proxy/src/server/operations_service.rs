// Copyright 2020 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::sync::Arc;

use ginepro::LoadBalancedChannel;
use grpc_util::auth::{AuthScheme, Permissions};
use protos::google::longrunning::{
    operations_client::OperationsClient, operations_server::Operations, CancelOperationRequest,
    DeleteOperationRequest, GetOperationRequest, ListOperationsRequest, ListOperationsResponse,
    Operation, WaitOperationRequest,
};
use tonic::metadata::MetadataMap;
use tonic::{Request, Response, Status};

use execution_util::instance_name_from_operation_name;

use crate::server::{client_call, ProxyServerInner};

pub(crate) struct OperationsService {
    inner: Arc<ProxyServerInner>,
    auth_scheme: AuthScheme,
}

impl OperationsService {
    pub const SERVICE_NAME: &'static str = "google.longrunning.Operations";

    pub(crate) fn new(inner: Arc<ProxyServerInner>, auth_scheme: AuthScheme) -> Self {
        OperationsService { inner, auth_scheme }
    }

    fn get_client(
        &self,
        metadata: &MetadataMap,
        operation_name: &str,
    ) -> Result<OperationsClient<LoadBalancedChannel>, Status> {
        let requested_instance_name = instance_name_from_operation_name(&operation_name.to_owned())
            .map_err(Status::invalid_argument)?;

        self.inner.check_authorized(
            self.auth_scheme,
            metadata,
            &requested_instance_name,
            Permissions::Execute,
        )?;

        self.inner
            .backend(&requested_instance_name)
            .operations
            .as_ref()
            .cloned()
            .ok_or_else(|| {
                Status::invalid_argument(format!("No such instance: {requested_instance_name}"))
            })
    }
}

#[tonic::async_trait]
impl Operations for OperationsService {
    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn list_operations(
        &self,
        request: Request<ListOperationsRequest>,
    ) -> Result<Response<ListOperationsResponse>, Status> {
        let client = self.get_client(request.metadata(), &request.get_ref().name)?;
        let request = request.into_inner();
        client_call(
            client,
            move |mut client| {
                let request = request.clone();
                async move { client.list_operations(request).await }
            },
            Self::SERVICE_NAME,
            "ListOperations",
        )
        .await
    }

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn get_operation(
        &self,
        request: Request<GetOperationRequest>,
    ) -> Result<Response<Operation>, Status> {
        let client = self.get_client(request.metadata(), &request.get_ref().name)?;
        let request = request.into_inner();
        client_call(
            client,
            move |mut client| {
                let request = request.clone();
                async move { client.get_operation(request).await }
            },
            Self::SERVICE_NAME,
            "GetOperation",
        )
        .await
    }

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn delete_operation(
        &self,
        request: Request<DeleteOperationRequest>,
    ) -> Result<Response<()>, Status> {
        let client = self.get_client(request.metadata(), &request.get_ref().name)?;
        let request = request.into_inner();
        client_call(
            client,
            move |mut client| {
                let request = request.clone();
                async move { client.delete_operation(request).await }
            },
            Self::SERVICE_NAME,
            "DeleteOperation",
        )
        .await
    }

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn cancel_operation(
        &self,
        request: Request<CancelOperationRequest>,
    ) -> Result<Response<()>, Status> {
        let client = self.get_client(request.metadata(), &request.get_ref().name)?;
        let request = request.into_inner();
        client_call(
            client,
            move |mut client| {
                let request = request.clone();
                async move { client.cancel_operation(request).await }
            },
            Self::SERVICE_NAME,
            "CancelOperation",
        )
        .await
    }

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn wait_operation(
        &self,
        request: Request<WaitOperationRequest>,
    ) -> Result<Response<Operation>, Status> {
        let client = self.get_client(request.metadata(), &request.get_ref().name)?;
        let request = request.into_inner();
        client_call(
            client,
            move |mut client| {
                let request = request.clone();
                async move { client.wait_operation(request).await }
            },
            Self::SERVICE_NAME,
            "WaitOperation",
        )
        .await
    }
}
