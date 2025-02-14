// Copyright 2020 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use protos::google::longrunning::{
    operations_server::Operations, CancelOperationRequest, DeleteOperationRequest,
    GetOperationRequest, ListOperationsRequest, ListOperationsResponse, Operation,
    WaitOperationRequest,
};
use tonic::{Request, Response, Status};

use execution_util::instance_name_from_operation_name;

use crate::api::ExecutionServer;

/// NB: This interface is only implementated in order to support client side cancellation of
/// operations, and so many methods are stubbed.
#[tonic::async_trait]
impl Operations for ExecutionServer {
    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn cancel_operation(
        &self,
        request: Request<CancelOperationRequest>,
    ) -> Result<Response<()>, Status> {
        let request = request.into_inner();
        let instance_name =
            instance_name_from_operation_name(&request.name).map_err(Status::invalid_argument)?;
        self.instances.instance(instance_name).cancel(request.name);
        Ok(Response::new(()))
    }

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn list_operations(
        &self,
        _request: Request<ListOperationsRequest>,
    ) -> Result<Response<ListOperationsResponse>, Status> {
        Err(Status::unimplemented("list_operations"))
    }

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn get_operation(
        &self,
        _request: Request<GetOperationRequest>,
    ) -> Result<Response<Operation>, Status> {
        Err(Status::unimplemented("get_operation"))
    }

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn delete_operation(
        &self,
        _request: Request<DeleteOperationRequest>,
    ) -> Result<Response<()>, Status> {
        Err(Status::unimplemented("delete_operation"))
    }

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn wait_operation(
        &self,
        _request: Request<WaitOperationRequest>,
    ) -> Result<Response<Operation>, Status> {
        Err(Status::unimplemented("wait_operation"))
    }
}
