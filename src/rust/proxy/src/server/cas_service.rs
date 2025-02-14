// Copyright 2020 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::sync::Arc;

use ginepro::LoadBalancedChannel;
use grpc_util::auth::{AuthScheme, Permissions};
use protos::build::bazel::remote::execution::v2::{
    content_addressable_storage_client::ContentAddressableStorageClient,
    content_addressable_storage_server::ContentAddressableStorage, BatchReadBlobsRequest,
    BatchReadBlobsResponse, BatchUpdateBlobsRequest, BatchUpdateBlobsResponse,
    FindMissingBlobsRequest, FindMissingBlobsResponse, GetTreeRequest, GetTreeResponse,
};
use tonic::metadata::MetadataMap;
use tonic::{Request, Response, Status};

use crate::server::{client_call, ProxyServerInner};

pub(crate) struct CasService {
    inner: Arc<ProxyServerInner>,
    auth_scheme: AuthScheme,
}

impl CasService {
    pub const SERVICE_NAME: &'static str =
        "build.bazel.remote.execution.v2.ContentAddressableStorage";

    pub(crate) fn new(inner: Arc<ProxyServerInner>, auth_scheme: AuthScheme) -> Self {
        CasService { inner, auth_scheme }
    }

    fn get_client(
        &self,
        metadata: &MetadataMap,
        requested_instance_name: &str,
        required_permissions: Permissions,
    ) -> Result<ContentAddressableStorageClient<LoadBalancedChannel>, Status> {
        self.inner.check_authorized(
            self.auth_scheme,
            metadata,
            requested_instance_name,
            required_permissions,
        )?;
        Ok(self.inner.backend(requested_instance_name).cas.clone())
    }
}

#[tonic::async_trait]
impl ContentAddressableStorage for CasService {
    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn find_missing_blobs(
        &self,
        request: Request<FindMissingBlobsRequest>,
    ) -> Result<Response<FindMissingBlobsResponse>, Status> {
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
                async move { client.find_missing_blobs(request).await }
            },
            Self::SERVICE_NAME,
            "FindMissingBlobs",
        )
        .await
    }

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn batch_update_blobs(
        &self,
        request: Request<BatchUpdateBlobsRequest>,
    ) -> Result<Response<BatchUpdateBlobsResponse>, Status> {
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
                async move { client.batch_update_blobs(request).await }
            },
            Self::SERVICE_NAME,
            "BatchUpdateBlobs",
        )
        .await
    }

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn batch_read_blobs(
        &self,
        request: Request<BatchReadBlobsRequest>,
    ) -> Result<Response<BatchReadBlobsResponse>, Status> {
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
                async move { client.batch_read_blobs(request).await }
            },
            Self::SERVICE_NAME,
            "BatchReadBlobs",
        )
        .await
    }

    type GetTreeStream = tonic::codec::Streaming<GetTreeResponse>;

    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn get_tree(
        &self,
        request: Request<GetTreeRequest>,
    ) -> Result<Response<Self::GetTreeStream>, Status> {
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
                async move { client.get_tree(request).await }
            },
            Self::SERVICE_NAME,
            "GetTree",
        )
        .await
    }
}
