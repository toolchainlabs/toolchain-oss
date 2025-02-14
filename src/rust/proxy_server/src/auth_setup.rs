// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).
use std::collections::HashMap;
use std::time::Duration;

use crate::config::AuthTokenMappingConfig;
use grpc_util::auth::{deserialize_jwk_set, AuthToken, AuthTokenEntry, JWKSet};
use proxy::ProxyServer;

pub async fn read_jwk_set(jwk_set_path: &str) -> Result<JWKSet, String> {
    let secret_json = tokio::fs::read_to_string(jwk_set_path)
        .await
        .map_err(|err| format!("Failed to read JWT keys from {jwk_set_path}: {err}"))?;
    let jwk_json = grpc_util::secrets::parse_secret(secret_json.as_bytes())?;
    let jwk_set = deserialize_jwk_set(&jwk_json).map_err(|e| format!("{e}"))?;
    log::info!(
        "Loaded JWT key IDs: {}",
        jwk_set
            .keys
            .iter()
            .map(|k| k.common.key_id.as_deref().unwrap_or("N/A"))
            .collect::<Vec<_>>()
            .join(", ")
    );
    Ok(jwk_set)
}

pub async fn get_auth_token_mapping_version(
    bucket: &s3::Bucket,
    s3_auth_token_mapping_path: &str,
) -> Result<String, String> {
    let (head_result, code) = bucket
        .head_object(s3_auth_token_mapping_path)
        .await
        .map_err(|e| format!("{e}"))?;
    if code != 200 {
        return Err(format!("HEAD operation for S3 was not 200: {code}"));
    }
    head_result
        .version_id
        .ok_or_else(|| "Version metadata was empty for the S3 object".to_owned())
}

pub async fn read_auth_token_mapping(
    bucket: &s3::Bucket,
    s3_auth_token_mapping_path: &str,
) -> Result<HashMap<AuthToken, AuthTokenEntry>, String> {
    let s3_obj = bucket
        .get_object(s3_auth_token_mapping_path)
        .await
        .map_err(|e| format!("{e}"))?;
    let mapping: HashMap<AuthToken, AuthTokenEntry> =
        serde_json::from_slice(s3_obj.bytes()).map_err(|e| format!("{e}"))?;
    log::info!(
        "Loaded auth token file with token IDs: {}",
        mapping
            .values()
            .map(|e| e.id.clone())
            .collect::<Vec<_>>()
            .join(", ")
    );
    Ok(mapping)
}

pub async fn refresh_auth_token_mapping(
    s3_bucket: s3::Bucket,
    config: AuthTokenMappingConfig,
    auth_token_mapping_initial_version: String,
    proxy_server: ProxyServer,
) {
    let duration = Duration::from_secs(config.refresh_frequency_s.unwrap_or(20));
    let mut interval = tokio::time::interval(duration);
    let mut version = auth_token_mapping_initial_version;
    loop {
        interval.tick().await;
        match get_auth_token_mapping_version(&s3_bucket, &config.s3_path).await {
            Ok(new_version) => {
                if new_version == version {
                    continue;
                }
                version = new_version;
                match read_auth_token_mapping(&s3_bucket, &config.s3_path).await {
                    Ok(mapping) => {
                        proxy_server.swap_auth_token_mapping(mapping);
                    }
                    Err(e) => log_auth_token_failure(e),
                }
            }
            Err(e) => log_auth_token_failure(e),
        }
    }
}

pub fn log_auth_token_failure(e: String) {
    metrics::increment_counter!("auth_token_mapping_refresh_failure");
    log::error!("auth_failure: Could not read auth token mapping from S3. Error: {e:?}");
}
