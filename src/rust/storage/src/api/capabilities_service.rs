// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::sync::Arc;

use protos::build::bazel::remote::execution::v2::{
    capabilities_server::Capabilities, digest_function::Value as DigestFunction_Value,
    ActionCacheUpdateCapabilities, CacheCapabilities, GetCapabilitiesRequest, ServerCapabilities,
};
use tonic::{Request, Response, Status};

use crate::api::InnerServer;

pub(super) struct CapabilitiesService {
    pub(super) inner: Arc<InnerServer>,
}

#[tonic::async_trait]
impl Capabilities for CapabilitiesService {
    #[tracing::instrument(skip_all, fields(opentelemetry = true))]
    async fn get_capabilities(
        &self,
        _request: Request<GetCapabilitiesRequest>,
    ) -> Result<Response<ServerCapabilities>, Status> {
        let response = ServerCapabilities {
            cache_capabilities: Some(CacheCapabilities {
                digest_function: vec![DigestFunction_Value::Sha256 as i32],
                max_batch_total_size_bytes: self.inner.max_batch_total_size_bytes as i64,
                action_cache_update_capabilities: Some(ActionCacheUpdateCapabilities {
                    // TODO: This should be set based on checking whether the client is
                    // authorized to write to the Action Cache.
                    update_enabled: true,
                }),
                ..CacheCapabilities::default()
            }),
            ..ServerCapabilities::default()
        };

        Ok(Response::new(response))
    }
}
