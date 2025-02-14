// Copyright 2020 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::collections::HashMap;
use std::time::Duration;

use grpc_util::backend::BackendConfig;
use grpc_util::infra::{GrpcConfig, InfraConfig};
use proxy::{BackendTimeoutsConfig, InstanceConfig, InstanceName, ListenAddressConfig};
use serde::Deserialize;

#[derive(Deserialize, Debug, Default)]
pub struct ProxyTimeoutsConfig {
    /// Timeout for GetActionResult API in milliseconds.
    pub get_action_result: Option<u64>,
}

impl ProxyTimeoutsConfig {
    pub fn into_backend_timeouts(self) -> BackendTimeoutsConfig {
        BackendTimeoutsConfig {
            get_action_result: self.get_action_result.map(Duration::from_millis),
        }
    }
}

#[derive(Deserialize, Clone, Debug, Default)]
pub struct AuthTokenMappingConfig {
    pub s3_bucket: String,
    pub s3_region: String,
    pub s3_path: String,
    pub refresh_frequency_s: Option<u64>,
}

#[derive(Deserialize, Debug, Default)]
pub struct Config {
    /// Which IP addresses to listen to for connections.
    pub listen_addresses: Vec<ListenAddressConfig>,

    /// The path to the rotable secret(s) storing the JWK set to be used when validating JWT tokens.
    pub jwk_set_path: String,

    /// Config for a JSON file mapping token strings to their metadata.
    ///
    /// If not set, no auth tokens will be loaded. Clients can still send requests with auth tokens,
    /// but no tokens will be recognized.
    pub auth_token_mapping: Option<AuthTokenMappingConfig>,

    /// Map of backend names to the ADDRESS:PORT of the backend. The backend names are
    /// referenced later as a service name. This allows defining addresses once and reusing
    /// throughout the config.
    pub backends: HashMap<String, BackendConfig>,

    /// Defines per-instance backends to use for each service.
    pub per_instance_backends: Option<HashMap<InstanceName, InstanceConfig>>,

    /// Defines the default backends to use for each service (if no per-instance backend is
    /// configured).
    pub default_backends: InstanceConfig,

    /// Admin endpoints configuration.
    pub infra: Option<InfraConfig>,

    /// gRPC configuration.
    pub grpc: Option<GrpcConfig>,

    /// Backend timeouts configuration.
    pub backend_timeouts: Option<ProxyTimeoutsConfig>,
}

impl Config {
    pub fn from_str(raw_config: &str) -> Result<Config, String> {
        serde_yaml::from_str(raw_config).map_err(|e| format!("config parse error: {e}"))
    }
}
