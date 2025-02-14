// Copyright 2020 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::sync::Arc;

use ginepro::LoadBalancedChannel;
use protos::google::devtools::remoteworkers::v1test2::{
    bots_client::BotsClient, bots_server::Bots, BotSession, CreateBotSessionRequest,
    UpdateBotSessionRequest,
};
use tonic::metadata::MetadataMap;
use tonic::{Request, Response, Status};

use crate::server::{client_call, ProxyServerInner};
use grpc_util::auth::{AuthScheme, Permissions};

pub(crate) struct BotsService {
    inner: Arc<ProxyServerInner>,
    auth_scheme: AuthScheme,
}

impl BotsService {
    pub const SERVICE_NAME: &'static str = "google.longrunning.Bots";

    pub(crate) fn new(inner: Arc<ProxyServerInner>, auth_scheme: AuthScheme) -> Self {
        BotsService { inner, auth_scheme }
    }

    /// The buildgrid server prefixes each BotSession's name with its instance name:
    /// https://gitlab.com/BuildGrid/buildgrid/-/blob/c6e43834e37b918246e566af4b459030f549a92e/buildgrid/server/bots/instance.py#L183
    fn instance_name_from_session_name(request: &UpdateBotSessionRequest) -> Result<&str, String> {
        let session_name = &request
            .bot_session
            .as_ref()
            .ok_or("No bot_session in `UpdateBotSessionRequest`")?
            .name;
        session_name
            .split_once('/')
            .map(|(instance, _)| instance)
            .ok_or_else(|| format!("unable to parse instance name from `{session_name}`"))
    }

    fn get_client(
        &self,
        metadata: &MetadataMap,
        requested_instance_name: &str,
    ) -> Result<BotsClient<LoadBalancedChannel>, Status> {
        self.inner.check_authorized(
            self.auth_scheme,
            metadata,
            requested_instance_name,
            // TODO: consider adding a Worker permission. Right now, the auth_token scheme does not
            // have any notion of permissions/entitlements because it was seen as unnecessary. So,
            // this value gets ignored.
            Permissions::Execute,
        )?;

        self.inner
            .backend(requested_instance_name)
            .bots
            .as_ref()
            .cloned()
            .ok_or_else(|| {
                Status::invalid_argument(format!("No such instance: {requested_instance_name}"))
            })
    }
}

/// NB: Some server implementations (notably `buildgrid`) use gRPC request deadlines to drive their
/// implementation of long-polling, by introspecting the deadline and ensuring that they return to
/// the client before the deadline is reached. Because we internally retry requests in this proxy,
/// we cannot pass the `tonic::Request` object through directly (because it is not `Clone`), and
/// instead create a new `Request` per retry attempt. While doing so, we need to preserve the
/// deadline, which would otherwise be lost. In future versions of `tonic` (0.8.3>=), we can use
/// `tonic::Request::{into_parts,from_parts}` instead.
#[tonic::async_trait]
impl Bots for BotsService {
    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn create_bot_session(
        &self,
        mut request: Request<CreateBotSessionRequest>,
    ) -> Result<Response<BotSession>, Status> {
        // See the note regarding deadlines on the trait implementation.
        let deadline = request.metadata_mut().remove("grpc-timeout");
        let client = self.get_client(request.metadata(), &request.get_ref().parent)?;
        let request = request.into_inner();
        client_call(
            client,
            move |mut client| {
                let mut request = Request::new(request.clone());
                if let Some(deadline) = deadline.as_ref() {
                    request
                        .metadata_mut()
                        .insert("grpc-timeout", deadline.clone());
                }
                async move { client.create_bot_session(request).await }
            },
            Self::SERVICE_NAME,
            "CreateBotSession",
        )
        .await
    }

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn update_bot_session(
        &self,
        mut request: Request<UpdateBotSessionRequest>,
    ) -> Result<Response<BotSession>, Status> {
        // See the note regarding deadlines on the trait implementation.
        let deadline = request.metadata_mut().remove("grpc-timeout");
        let requested_instance_name = Self::instance_name_from_session_name(request.get_ref())
            .map_err(Status::invalid_argument)?;

        let client = self.get_client(request.metadata(), requested_instance_name)?;
        let request = request.into_inner();
        client_call(
            client,
            move |mut client| {
                let mut request = Request::new(request.clone());
                if let Some(deadline) = deadline.as_ref() {
                    request
                        .metadata_mut()
                        .insert("grpc-timeout", deadline.clone());
                }
                async move { client.update_bot_session(request).await }
            },
            Self::SERVICE_NAME,
            "UpdateBotSession",
        )
        .await
    }
}
