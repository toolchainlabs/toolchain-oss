// Copyright 2022 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use ginepro::LoadBalancedChannel;
use serde::Deserialize;

#[derive(Deserialize, Debug)]
pub struct BackendConfig {
    /// ADDRESS:PORT of this backend.
    pub address: String,

    /// Number of concurrent connections to maintain to this backend.
    #[serde(default = "default_connections")]
    pub connections: usize,
}

fn default_connections() -> usize {
    1
}

impl Default for BackendConfig {
    fn default() -> Self {
        BackendConfig {
            address: String::new(),
            connections: default_connections(),
        }
    }
}

pub async fn construct_channel(config: BackendConfig) -> Result<LoadBalancedChannel, String> {
    let (hostname, port_str) = match config.address.split_once(':') {
        Some((h, p)) => (h, p),
        None => return Err("Expected NAME:PORT".to_owned()),
    };
    if hostname.is_empty() || port_str.is_empty() {
        return Err("Expected NAME:PORT".to_owned());
    }
    let port: u16 = match port_str.parse() {
        Ok(p) => p,
        Err(_) => return Err("Unable to parse port".into()),
    };
    let service_definition = match ginepro::ServiceDefinition::from_parts(hostname, port) {
        Ok(sd) => sd,
        Err(err) => {
            return Err(format!(
                "failed to initialize ginepro ServiceDefinition: {err}"
            ))
        }
    };

    ginepro::LoadBalancedChannel::builder(service_definition)
        .channel()
        .await
        .map_err(|err| format!("failed to initialize channel: {err}"))
}
