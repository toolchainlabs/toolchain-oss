// Copyright 2022 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

mod bots_service;
mod capabilities_service;
mod execution_service;
mod operations_service;

use ginepro::LoadBalancedChannel;

use protos::build::bazel::remote::execution::v2::content_addressable_storage_client::ContentAddressableStorageClient;

use crate::server::Instances;

#[derive(Clone)]
pub struct ExecutionServer {
    instances: Instances,
    cas_client: ContentAddressableStorageClient<LoadBalancedChannel>,
}

impl ExecutionServer {
    pub fn new(cas_client: ContentAddressableStorageClient<LoadBalancedChannel>) -> Self {
        Self {
            instances: Instances::default(),
            cas_client,
        }
    }

    pub fn update_gauges(&self) {
        self.instances.update_gauges();
    }
}
