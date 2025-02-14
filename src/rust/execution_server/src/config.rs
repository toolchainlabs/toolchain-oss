// Copyright 2022 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::str::FromStr;

use grpc_util::backend::BackendConfig;
use grpc_util::infra::{GrpcConfig, InfraConfig};
use serde::Deserialize;

#[derive(Deserialize, Debug)]
pub struct Config {
    /// IP address on which to listen for connections.
    pub listen_address: String,

    /// Admin endpoints configuration.
    pub infra: Option<InfraConfig>,

    /// gRPC configuration.
    pub grpc: Option<GrpcConfig>,

    /// Configuration for the connection to the CAS.
    pub cas: BackendConfig,
}

impl FromStr for Config {
    type Err = String;

    fn from_str(raw_config: &str) -> Result<Self, Self::Err> {
        serde_yaml::from_str(raw_config).map_err(|e| format!("config parse error: {e}"))
    }
}
