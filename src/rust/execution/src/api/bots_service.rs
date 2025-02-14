// Copyright 2022 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use protos::google::devtools::remoteworkers::v1test2::{
    bots_server::Bots, BotSession, CreateBotSessionRequest, UpdateBotSessionRequest,
};
use tonic::{Request, Response, Status};

use execution_util::{generate_session_name, instance_name_from_session_name};

use crate::api::ExecutionServer;
use crate::BOT_POLL_TIMEOUT;

#[tonic::async_trait]
impl Bots for ExecutionServer {
    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn create_bot_session(
        &self,
        request: Request<CreateBotSessionRequest>,
    ) -> Result<Response<BotSession>, Status> {
        let request = request.into_inner();
        let instance_name = request.parent;
        let mut session = request
            .bot_session
            .ok_or_else(|| Status::invalid_argument("no `bot_session` was set."))?;

        session.name = generate_session_name(&instance_name);

        self.instances
            .instance(instance_name)
            .poll(&mut session, BOT_POLL_TIMEOUT)
            .await;

        Ok(Response::new(session))
    }

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn update_bot_session(
        &self,
        request: Request<UpdateBotSessionRequest>,
    ) -> Result<Response<BotSession>, Status> {
        let request = request.into_inner();
        let mut session = request.bot_session.ok_or_else(|| {
            Status::invalid_argument("No bot_session in `UpdateBotSessionRequest`")
        })?;

        let instance_name =
            instance_name_from_session_name(&session.name).map_err(Status::invalid_argument)?;

        self.instances
            .instance(instance_name)
            .poll(&mut session, BOT_POLL_TIMEOUT)
            .await;

        Ok(Response::new(session))
    }
}
