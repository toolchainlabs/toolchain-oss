// Copyright 2022 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::pin::Pin;

use digest::{required_digest, Digest};
use futures::Stream;
use prost::Message;
use protos::build::bazel::remote::execution::v2::{
    execution_server::Execution, Action as ActionRequest, BatchReadBlobsRequest, ExecuteRequest,
    ExecuteResponse, WaitExecutionRequest,
};
use protos::google::longrunning::{operation, Operation};
use tokio::sync::watch;
use tonic::{Code, Request, Response, Status};

use execution_util::{instance_name_from_operation_name, InstanceName, OperationName};

use crate::any_proto_encode;
use crate::api::ExecutionServer;
use crate::server::ActionStatus;

type OperationStream = Pin<Box<dyn Stream<Item = Result<Operation, Status>> + Send + Sync>>;

#[tonic::async_trait]
impl Execution for ExecutionServer {
    type ExecuteStream = OperationStream;

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn execute(
        &self,
        request: Request<ExecuteRequest>,
    ) -> Result<Response<Self::ExecuteStream>, Status> {
        let request = request.into_inner();
        let instance = self.instances.instance(request.instance_name.clone());

        let action_digest = required_digest("action_digest", request.action_digest)
            .map_err(Status::invalid_argument)?;
        let action = self
            .load_action(request.instance_name, action_digest)
            .await?;

        let (operation_name, receiver) = instance.execute(action_digest, action);

        Ok(Response::new(stream_from_receiver(
            operation_name,
            receiver,
        )))
    }

    type WaitExecutionStream = OperationStream;

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn wait_execution(
        &self,
        request: Request<WaitExecutionRequest>,
    ) -> Result<Response<Self::WaitExecutionStream>, Status> {
        let operation_name = request.into_inner().name;
        let instance_name =
            instance_name_from_operation_name(&operation_name).map_err(Status::invalid_argument)?;

        let receiver = self
            .instances
            .instance(instance_name)
            .wait(&operation_name)
            .ok_or_else(|| Status::not_found("no known operation named {operation_name}"))?;

        Ok(Response::new(stream_from_receiver(
            operation_name,
            receiver,
        )))
    }
}

impl ExecutionServer {
    // TODO: Add retry.
    async fn load_action(
        &self,
        instance_name: InstanceName,
        action_digest: Digest,
    ) -> Result<ActionRequest, Status> {
        let mut responses = self
            .cas_client
            .clone()
            .batch_read_blobs(BatchReadBlobsRequest {
                instance_name,
                digests: vec![action_digest.into()],
            })
            .await?
            .into_inner();

        let Some(response) = responses.responses.pop() else {
            return Err(Status::internal(format!("Wrong number of responses: {}", responses.responses.len())));
        };

        match response.status {
            Some(status) if status.code != Code::Ok as i32 => {
                return Err(Status::new(Code::from_i32(status.code), status.message))
            }
            None => return Err(Status::internal("No status on read result.")),
            _ => (),
        }

        ActionRequest::decode(response.data)
            .map_err(|e| Status::internal(format!("Could not decode action: {e}")))
    }
}

fn stream_from_receiver(
    name: OperationName,
    mut receiver: watch::Receiver<ActionStatus>,
) -> OperationStream {
    let stream = async_stream::stream! {
      let item = loop {
          let value = (*receiver.borrow()).clone();
          match value {
            ActionStatus::Running(eom) => {
              yield Ok(Operation {
                name: name.clone(),
                done: false,
                metadata: Some(any_proto_encode(&eom)),
                ..Default::default()
              });
            },
            ActionStatus::Completed(item) => break Some(item),
          }

          if let Err(_recv_error) = receiver.changed().await {
            break None
          }
      };

      let (status, result) = match item {
        Some(Ok(action_result)) => {
          let status = protos::google::rpc::Status {
            code: Code::Ok as i32,
            ..Default::default()
          };
          (status, Some(action_result))
        }
        Some(Err(status)) => {
          let status = protos::google::rpc::Status {
            code: status.code() as i32,
            message: status.message().to_owned(),
            ..Default::default()
          };
          (status, None)
        }
        None => {
          let status = protos::google::rpc::Status {
            code: Code::Cancelled as i32,
            ..Default::default()
          };
          (status, None)
        }
      };

      yield Ok(Operation {
        name,
        done: true,
        result: Some(
          operation::Result::Response(any_proto_encode(
            &ExecuteResponse {
              result,
              status: Some(status),
              ..Default::default()
            },
          )),
        ),
        ..Default::default()
      });
    };
    Box::pin(stream)
}
