// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::collections::HashMap;
use std::num::NonZeroUsize;
use std::str::FromStr;

use grpc_util::infra::{GrpcConfig, InfraConfig};
use serde::Deserialize;

/// Preferred size of chunks written to storage.
pub const DEFAULT_CHUNK_SIZE: usize = 512 * 1024;

#[derive(Clone, Deserialize, Debug)]
pub struct LocalBlobStorageConfig {
    /// Base path under which to store blobs.
    pub base_path: String,
}

#[derive(Clone, Deserialize, Debug)]
pub struct SizeSplitStorageConfig {
    /// Blobs less than this size will be stored in the `smaller` storage.
    pub size: usize,

    /// Storage for "smaller" blobs.
    #[serde(with = "serde_yaml::with::singleton_map")]
    pub smaller: Box<BlobStorageConfig>,

    /// Storage for "larger" blobs.
    #[serde(with = "serde_yaml::with::singleton_map")]
    pub larger: Box<BlobStorageConfig>,
}

#[derive(Clone, Deserialize, Debug)]
pub struct ExistenceCacheStorageConfig {
    /// Maximum of number of digests to cache.
    pub max_entries: NonZeroUsize,

    /// The underlying storage driver.
    #[serde(with = "serde_yaml::with::singleton_map")]
    pub underlying: Box<BlobStorageConfig>,
}

#[derive(Clone, Deserialize, Debug)]
pub struct RedisBackendConfig {
    /// Address of the backend Redis cluster in `ADDRESS[:PORT]` format.
    /// Examples:
    /// - cache.example.com
    /// - cache.example.com:6379
    pub address: String,

    /// Address of any read-only replicas in the Redis cluster in `ADDRESS[:PORT]` format.
    /// This provides support for the "reader endpoint" supported by AWS Elasticache.
    pub read_only_address: Option<String>,

    /// Number of connections to use for new client.
    pub num_connections: Option<usize>,

    /// Probability of using primary for read-only traffic out of denominator of 1000.
    pub use_primary_for_read_only_probability: Option<usize>,
}

#[derive(Clone, Deserialize, Debug)]
pub struct RedisChunkedStorageConfig {
    /// Name of the Redis backend to use.
    pub backend: String,

    /// Preferred size of written data chunks.
    pub write_chunk_size: Option<usize>,

    /// Prefix to prepend to all Redis keys.
    pub prefix: Option<String>,
}

#[derive(Clone, Deserialize, Debug)]
pub struct RedisDirectStorageConfig {
    /// Name of the Redis backend to use.
    pub backend: String,

    /// Prefix to prepend to all Redis keys.
    pub prefix: Option<String>,
}

#[derive(Clone, Deserialize, Debug)]
pub struct DarkLaunchConfig {
    /// REAPI instance names to send to storage2.
    pub storage2_instance_names: Vec<String>,

    /// Write to secondary backend when enabled.
    pub write_to_secondary: Option<bool>,

    /// Storage #1
    #[serde(with = "serde_yaml::with::singleton_map")]
    pub storage1: Box<BlobStorageConfig>,

    /// Storage #2
    #[serde(with = "serde_yaml::with::singleton_map")]
    pub storage2: Box<BlobStorageConfig>,
}

#[derive(Clone, Deserialize, Debug)]
pub struct ShardConfig {
    /// Shard key to use for this shard. This will be hashed to determine the subset of
    /// the hash ring that this shard is responsible for.
    pub shard_key: String,

    /// Storage driver config for the storage driver serving this shard.
    #[serde(with = "serde_yaml::with::singleton_map")]
    pub storage: Box<BlobStorageConfig>,
}

#[derive(Clone, Deserialize, Debug)]
pub struct ShardedStorageConfig {
    /// List of shards to distribute operations over.
    pub shards: Vec<ShardConfig>,

    /// Number of shards including the primary shard to which the driver will distribute
    /// keys. With `num_replicas` == 2, a key would be distributed to the k'th and k+1'th
    /// shards.
    pub num_replicas: usize,
}

#[derive(Clone, Deserialize, Debug)]
pub struct ReadCacheStorageConfig {
    /// Storage config for the "fast" storage driver.
    #[serde(with = "serde_yaml::with::singleton_map")]
    pub fast: Box<SmallBlobStorageConfig>,

    /// Storage config for the "slow" storage driver.
    #[serde(with = "serde_yaml::with::singleton_map")]
    pub slow: Box<BlobStorageConfig>,
}

#[derive(Deserialize)]
pub struct AmberfloApiKeyFile {
    /// API key to use when interacting with Amberflo API.
    pub api_key: String,
}

#[derive(Clone, Deserialize, Debug)]
pub struct AmberfloBackendConfig {
    /// Prefix to add to all customer IDs.
    pub customer_id_prefix: String,

    /// File that stores the API key (JSON object with `api_key` key.)
    pub api_key_file: String,

    /// Duration of the aggregation window in seconds.
    pub aggregation_window_duration_secs: usize,

    /// Environment dimension to send with events.
    pub env_dimension: String,

    /// URL to the Amberflo API endpoint for ingesting metrics.
    pub api_ingest_url: Option<String>,
}

#[derive(Clone, Deserialize, Debug)]
#[serde(rename_all = "snake_case")]
pub enum BlobStorageConfig {
    Local(LocalBlobStorageConfig),
    Memory,
    SizeSplit(SizeSplitStorageConfig),
    RedisChunked(RedisChunkedStorageConfig),
    RedisDirect(RedisDirectStorageConfig),
    ExistenceCache(ExistenceCacheStorageConfig),
    DarkLaunch(DarkLaunchConfig),
    ReadDigestVerifier(Box<BlobStorageConfig>),
    Metered(Box<BlobStorageConfig>),
    Sharded(ShardedStorageConfig),
    ReadCache(ReadCacheStorageConfig),
    Null,
    AlwaysErrors,
}

#[derive(Clone, Deserialize, Debug)]
#[serde(rename_all = "snake_case")]
pub enum SmallBlobStorageConfig {
    RedisDirect(RedisDirectStorageConfig),
    Sharded(ShardedStorageConfig),
    Null,
    AlwaysErrors,
}

#[derive(Clone, Deserialize, Debug)]
pub struct Config {
    /// IP address on which to listen for connections.
    pub listen_address: String,

    /// CAS configuration
    #[serde(with = "serde_yaml::with::singleton_map")]
    pub cas: BlobStorageConfig,

    /// Action Cache configuration
    #[serde(with = "serde_yaml::with::singleton_map")]
    pub action_cache: BlobStorageConfig,

    /// Admin endpoints configuration.
    pub infra: Option<InfraConfig>,

    /// gRPC configuration.
    pub grpc: Option<GrpcConfig>,

    /// Redis backends
    pub redis_backends: Option<HashMap<String, RedisBackendConfig>>,

    /// Check action cache completeness.
    pub check_action_cache_completeness: Option<bool>,

    /// Probability of checking action cache completeness. Stored as integer in range 0-1000.
    pub completeness_check_probability: Option<u32>,

    /// Amberflo backend config
    pub amberflo_backend: Option<AmberfloBackendConfig>,
}

impl FromStr for Config {
    type Err = String;

    fn from_str(raw_config: &str) -> Result<Self, Self::Err> {
        serde_yaml::from_str(raw_config).map_err(|e| format!("config parse error: {e}"))
    }
}
