// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

#![deny(warnings)]

use std::collections::HashMap;
use std::env;
use std::net::SocketAddr;
use std::num::NonZeroUsize;
use std::str::FromStr;
use std::time::Duration;

use bytes::Bytes;
use clap::{Arg, Command};
use futures::future::BoxFuture;
use futures::FutureExt;
use grpc_util::hyper::AddrIncomingWithStream;
use grpc_util::infra::setup_infra_endpoints;
use grpc_util::logging::setup_logging;
use grpc_util::sentry::setup_sentry;
use hyper::server::conn::AddrIncoming;
use itertools::Itertools;
use redis::{ConnectionAddr, ConnectionInfo, RedisConnectionInfo};
use storage::api::Server;
use storage::driver::redis::common::{ClientWrapper, ConnectionGetter};
use storage::driver::redis::pool::AsyncRedisConnectionPool;
use storage::driver::redis::RedisConnectionName;
use storage::driver::{
    AlwaysErrorsStorage, AmberfloEmitter, BlobStorage, BlobStorageAdapter, ChunkingStorage,
    DarkLaunchStorage, ExistenceCacheStorage, FastSlowReplicationStorage, FileBackedStorage,
    MemoryStorage, MeteredStorage, MetricsMonitoredStorage, NullStorage, ReadDigestVerifier,
    RedisBackend, RedisDirectStorage, RedisStorage, ShardingStorage, SizeSplitStorage,
    SmallBlobStorage, SmallBlobStorageAdapter, WriteDigestVerifier,
};
use storage::uuid_gen::DefaultUuidGenerator;
use storage::Digest;
use tokio::io::AsyncReadExt;
use tower_http::metrics::in_flight_requests::InFlightRequestsCounter;

use crate::config::{
    AmberfloApiKeyFile, BlobStorageConfig, RedisBackendConfig, ShardedStorageConfig,
    SmallBlobStorageConfig,
};

pub mod config;

const DEFAULT_REDIS_PORT: u16 = 6379;

type BoxBlobStorage = Box<dyn BlobStorage + Send + Sync + 'static>;
type BoxSmallBlobStorage = Box<dyn SmallBlobStorage + Send + Sync + 'static>;

fn parse_redis_addr(address: &str, backend_name: &str) -> Result<ConnectionInfo, String> {
    let (address, port) = match address.split(':').collect::<Vec<_>>().as_slice() {
        [addr, port] => {
            let port: u16 = (*port).parse().map_err(|err| {
                format!(
                    "Redis setup error for backend '{}': Failed to parse port {}: {}",
                    backend_name, *port, err
                )
            })?;
            (*addr, port)
        }
        [addr] => (*addr, DEFAULT_REDIS_PORT),
        _ => {
            return Err(format!(
                "Redis setup error for backend '{backend_name}': Failed to parse address: {address}",
            ));
        }
    };

    Ok(ConnectionInfo {
        addr: ConnectionAddr::Tcp(address.to_string(), port),
        redis: RedisConnectionInfo {
            db: 0,
            username: None,
            password: None,
        },
    })
}

async fn verify_redis_backends(
    redis_backends: &HashMap<String, RedisBackend<AsyncRedisConnectionPool>>,
) -> Result<(), String> {
    for (name, backend) in redis_backends {
        backend
            .verify_connection()
            .await
            .map_err(|err| format!("Unable to verify connection with backend `{name}`: {err}"))?;
    }

    Ok(())
}

fn setup_redis_backends(
    config: Option<HashMap<String, RedisBackendConfig>>,
) -> Result<HashMap<String, RedisBackend<AsyncRedisConnectionPool>>, String> {
    let backend_configs = config.unwrap_or_default();
    let (redis_backends_by_name, errors): (Vec<_>, Vec<String>) = backend_configs
        .into_iter()
        .map(|(name, backend_config)| {
            let annotated_pool = {
                let primary_pool = {
                    let conn_info = parse_redis_addr(&backend_config.address, &name)?;
                    log::info!("primary pool addr = {conn_info:?}");
                    let client = redis::Client::open(conn_info)
                        .map_err(|err| format!("Redis setup error: {err}"))?;
                    let client_wrapper = ClientWrapper::new(
                        client,
                        RedisConnectionName {
                            backend: name.clone(),
                            endpoint: "primary",
                        },
                    );
                    AsyncRedisConnectionPool::new(
                        client_wrapper,
                        backend_config.num_connections.unwrap_or(20),
                        name.clone(),
                        "primary",
                    )
                };

                let read_only_pool_opt = backend_config
                    .read_only_address
                    .as_ref()
                    .map(|addr| -> Result<_, String> {
                        let conn_info = parse_redis_addr(addr, &name)?;
                        let client = redis::Client::open(conn_info)
                            .map_err(|err| format!("Redis setup error: {err}"))?;
                        let client_wrapper = ClientWrapper::new(
                            client,
                            RedisConnectionName {
                                backend: name.clone(),
                                endpoint: "read-only",
                            },
                        );

                        let async_pool = AsyncRedisConnectionPool::new(
                            client_wrapper,
                            backend_config.num_connections.unwrap_or(20),
                            name.clone(),
                            "read-only",
                        );
                        Ok(async_pool)
                    })
                    .transpose()?;

                RedisBackend::new(
                    name.clone(),
                    primary_pool,
                    read_only_pool_opt,
                    backend_config.use_primary_for_read_only_probability,
                )
            };
            Ok((name, annotated_pool))
        })
        .partition_result();

    if !errors.is_empty() {
        Err(format!("Redis setup errors: {}", errors.join(", ")))
    } else {
        Ok(redis_backends_by_name
            .into_iter()
            .collect::<HashMap<_, _>>())
    }
}

async fn make_sharding_storage<'a, P>(
    c: &ShardedStorageConfig,
    purpose: &'static str,
    redis_backends: &'a HashMap<String, P>,
    amberflo_emitter: Option<&'a AmberfloEmitter>,
) -> Result<impl BlobStorage, String>
where
    P: ConnectionGetter + Clone + Send + Sync + 'static,
{
    let mut shards: Vec<(Digest, BoxBlobStorage)> = Vec::new();
    let mut shard_descriptions = HashMap::new();
    for shard_config in &c.shards {
        let storage = make_storage(
            shard_config.storage.clone(),
            false,
            purpose,
            redis_backends,
            amberflo_emitter,
        )
        .await
        .map_err(|err| {
            format!(
                "Shard {} failed to construct: {err}",
                &shard_config.shard_key
            )
        })?;
        let shard_key = {
            // Note: The shard key only needs to be stable and deterministic. It
            // does not necessarily need to be, but `Digest` is stable and
            // deterministic so it used here.
            let bytes = Bytes::copy_from_slice(shard_config.shard_key.as_bytes());
            Digest::of_bytes(&bytes)?
        };
        shards.push((shard_key, storage));
        shard_descriptions.insert(shard_key, shard_config.shard_key.to_string());
    }
    let key_replicas: NonZeroUsize = c
        .num_replicas
        .try_into()
        .map_err(|_| "num_replicas must be non-zero".to_string())?;
    let storage = ShardingStorage::new(shards, key_replicas, purpose, shard_descriptions);
    Ok(MetricsMonitoredStorage::new(
        storage, "sharded", purpose, false,
    ))
}

fn make_storage<'a, P>(
    config: Box<BlobStorageConfig>,
    verify_digests: bool,
    purpose: &'static str,
    redis_backends: &'a HashMap<String, P>,
    amberflo_emitter: Option<&'a AmberfloEmitter>,
) -> BoxFuture<'a, Result<BoxBlobStorage, String>>
where
    P: ConnectionGetter + Clone + Send + Sync + 'static,
{
    (async move {
        let storage = match config.as_ref() {
            BlobStorageConfig::Local(c) => {
                let pod_namespace =
                    env::var("K8S_POD_NAMESPACE").expect("Expected K8S_POD_NAMESPACE to be set.");
                let pod_name = env::var("K8S_POD_NAME").expect("Expected K8S_POD_NAME to be set.");
                let container_id = format!("{pod_namespace}-{pod_name}");
                let storage = FileBackedStorage::new(c.base_path.clone(), &container_id)
                    .await
                    .map_err(String::from)?;
                let storage = MetricsMonitoredStorage::new(storage, "file", purpose, true);
                Box::new(storage) as BoxBlobStorage
            }
            BlobStorageConfig::Memory => {
                let storage = MemoryStorage::new();
                let storage = MetricsMonitoredStorage::new(storage, "memory", purpose, true);
                Box::new(storage) as BoxBlobStorage
            }
            BlobStorageConfig::SizeSplit(c) => {
                let storage1 = make_storage(
                    c.smaller.clone(),
                    false,
                    purpose,
                    redis_backends,
                    amberflo_emitter,
                )
                .await?;
                let storage2 = make_storage(
                    c.larger.clone(),
                    false,
                    purpose,
                    redis_backends,
                    amberflo_emitter,
                )
                .await?;
                let storage = SizeSplitStorage::new(c.size, storage1, storage2);
                let storage = MetricsMonitoredStorage::new(storage, "size_split", purpose, false);
                Box::new(storage) as BoxBlobStorage
            }
            BlobStorageConfig::RedisChunked(c) => {
                let pool = redis_backends
                    .get(&c.backend)
                    .ok_or_else(|| format!("Redis setup error: unknown backend: {}", &c.backend))?
                    .clone();
                let write_chunk_size = c.write_chunk_size.unwrap_or(config::DEFAULT_CHUNK_SIZE);
                let storage = RedisStorage::new(pool, c.prefix.clone(), DefaultUuidGenerator)
                    .await
                    .map_err(|err| format!("Redis setup error: {err}"))?;
                let storage = ChunkingStorage::new(storage, write_chunk_size);
                let storage = MetricsMonitoredStorage::new(storage, "redis", purpose, true);
                Box::new(storage) as BoxBlobStorage
            }
            BlobStorageConfig::RedisDirect(c) => {
                let storage = make_small_storage(
                    Box::new(SmallBlobStorageConfig::RedisDirect(c.clone())),
                    purpose,
                    redis_backends,
                    amberflo_emitter,
                )
                .await?;
                let storage = SmallBlobStorageAdapter::new(storage);
                Box::new(storage) as BoxBlobStorage
            }
            BlobStorageConfig::ExistenceCache(c) => {
                let underlying = make_storage(
                    c.underlying.clone(),
                    false,
                    purpose,
                    redis_backends,
                    amberflo_emitter,
                )
                .await?;
                let storage = ExistenceCacheStorage::new(c.max_entries, underlying);
                let storage =
                    MetricsMonitoredStorage::new(storage, "existence_cache", purpose, false);
                Box::new(storage) as BoxBlobStorage
            }
            BlobStorageConfig::DarkLaunch(c) => {
                let storage1 = make_storage(
                    c.storage1.clone(),
                    false,
                    purpose,
                    redis_backends,
                    amberflo_emitter,
                )
                .await?;
                let storage2 = make_storage(
                    c.storage2.clone(),
                    false,
                    purpose,
                    redis_backends,
                    amberflo_emitter,
                )
                .await?;
                let storage = DarkLaunchStorage::new(
                    storage1,
                    storage2,
                    c.storage2_instance_names.clone(),
                    c.write_to_secondary.unwrap_or(true),
                    purpose,
                );
                let storage = MetricsMonitoredStorage::new(storage, "dark_launch", purpose, false);
                Box::new(storage) as BoxBlobStorage
            }
            BlobStorageConfig::ReadDigestVerifier(c) => {
                let storage =
                    make_storage(c.clone(), false, purpose, redis_backends, amberflo_emitter)
                        .await?;
                let storage = ReadDigestVerifier::new(storage);
                Box::new(storage) as BoxBlobStorage
            }
            BlobStorageConfig::Metered(c) => {
                let storage =
                    make_storage(c.clone(), false, purpose, redis_backends, amberflo_emitter)
                        .await?;
                let storage = MeteredStorage::new(
                    storage,
                    amberflo_emitter
                        .ok_or_else(|| "Amberflo emitter must be configured".to_string())?
                        .sender(),
                );
                Box::new(storage) as BoxBlobStorage
            }
            BlobStorageConfig::Sharded(c) => {
                Box::new(make_sharding_storage(c, purpose, redis_backends, amberflo_emitter).await?)
                    as BoxBlobStorage
            }
            BlobStorageConfig::ReadCache(c) => {
                let fast_storage =
                    make_small_storage(c.fast.clone(), purpose, redis_backends, amberflo_emitter)
                        .await?;
                let slow_storage = make_storage(
                    c.slow.clone(),
                    false,
                    purpose,
                    redis_backends,
                    amberflo_emitter,
                )
                .await?;
                let storage = FastSlowReplicationStorage::new(fast_storage, slow_storage);
                let storage = SmallBlobStorageAdapter::new(storage);
                let storage = MetricsMonitoredStorage::new(storage, "fast_slow", purpose, false);
                Box::new(storage) as BoxBlobStorage
            }
            BlobStorageConfig::Null => {
                let storage = make_small_storage(
                    Box::new(SmallBlobStorageConfig::Null),
                    purpose,
                    redis_backends,
                    amberflo_emitter,
                )
                .await?;
                let storage = SmallBlobStorageAdapter::new(storage);
                Box::new(storage) as BoxBlobStorage
            }
            BlobStorageConfig::AlwaysErrors => {
                let storage = make_small_storage(
                    Box::new(SmallBlobStorageConfig::AlwaysErrors),
                    purpose,
                    redis_backends,
                    amberflo_emitter,
                )
                .await?;
                let storage = SmallBlobStorageAdapter::new(storage);
                Box::new(storage) as BoxBlobStorage
            }
        };

        if verify_digests {
            Ok(Box::new(WriteDigestVerifier::new(storage)) as BoxBlobStorage)
        } else {
            Ok(storage)
        }
    })
    .boxed()
}

fn make_small_storage<'a, P>(
    config: Box<SmallBlobStorageConfig>,
    purpose: &'static str,
    redis_backends: &'a HashMap<String, P>,
    amberflo_emitter: Option<&'a AmberfloEmitter>,
) -> BoxFuture<'a, Result<BoxSmallBlobStorage, String>>
where
    P: ConnectionGetter + Clone + Send + Sync + 'static,
{
    (async move {
        let storage = match config.as_ref() {
            SmallBlobStorageConfig::RedisDirect(c) => {
                let pool = redis_backends
                    .get(&c.backend)
                    .ok_or_else(|| format!("Redis setup error: unknown backend: {}", &c.backend))?
                    .clone();
                let storage = RedisDirectStorage::new(pool, c.prefix.clone())
                    .await
                    .map_err(|err| format!("Redis setup error: {err}"))?;
                let storage = MetricsMonitoredStorage::new(storage, "redis_direct", purpose, true);
                Box::new(storage) as BoxSmallBlobStorage
            }
            SmallBlobStorageConfig::Sharded(c) => {
                // TODO: It will likely eventually make sense to directly
                // `impl SmallBlobStorage for ShardingStorage`
                Box::new(BlobStorageAdapter::new(
                    make_sharding_storage(c, purpose, redis_backends, amberflo_emitter).await?,
                )) as BoxSmallBlobStorage
            }
            SmallBlobStorageConfig::Null => {
                let storage = NullStorage;
                let storage = MetricsMonitoredStorage::new(storage, "null", purpose, true);
                Box::new(storage) as BoxSmallBlobStorage
            }
            SmallBlobStorageConfig::AlwaysErrors => {
                let storage = AlwaysErrorsStorage;
                let storage = MetricsMonitoredStorage::new(storage, "always_errors", purpose, true);
                Box::new(storage) as BoxSmallBlobStorage
            }
        };

        Ok(storage)
    })
    .boxed()
}

fn scrape_redis_backend_metrics(
    redis_backends: &HashMap<String, RedisBackend<AsyncRedisConnectionPool>>,
) {
    for redis_backend in redis_backends.values() {
        redis_backend.update_gauges();
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let matches = Command::new("storage_server")
        .arg(
            Arg::new("config")
                .short('c')
                .required(true)
                .value_name("FILE"),
        )
        .get_matches();

    let config_filename = matches.get_one::<String>("config").unwrap();
    let mut file = tokio::fs::File::open(config_filename).await?;
    let mut config_str = String::new();
    file.read_to_string(&mut config_str).await?;
    let config = config::Config::from_str(&config_str).unwrap();

    setup_logging(config.infra.as_ref(), "storage_server");
    log::info!("Storage server config: {config:?}");
    let _sentry_guard = setup_sentry(config.infra.as_ref(), "storage_server");

    // Setup Redis backends and verify all connections to them. The unwrap call will panic if
    // there is an error from `verify_redis_backends`.
    let redis_backends = setup_redis_backends(config.redis_backends)?;
    verify_redis_backends(&redis_backends).await.unwrap();

    // Create an Amberflo emitter if configured.
    let amberflo_backend = match config.amberflo_backend {
        Some(c) => {
            let aggregation_window_duration =
                Duration::from_secs(c.aggregation_window_duration_secs as u64);
            let mut api_key_file = tokio::fs::File::open(c.api_key_file)
                .await
                .expect("Open Amberflo api key secret");
            let mut api_key_file_bytes = Vec::new();
            api_key_file
                .read_to_end(&mut api_key_file_bytes)
                .await
                .expect("read Amberflo api key secret");
            let api_key_wrapper: AmberfloApiKeyFile =
                serde_json::from_slice(&api_key_file_bytes).expect("Parse Amberflo api key file");
            Some(AmberfloEmitter::new(
                aggregation_window_duration,
                c.customer_id_prefix,
                c.env_dimension,
                api_key_wrapper.api_key,
                c.api_ingest_url,
            ))
        }
        None => None,
    };

    let cas = make_storage(
        Box::new(config.cas),
        true,
        "CAS",
        &redis_backends,
        amberflo_backend.as_ref(),
    )
    .await?;
    let action_cache = make_storage(
        Box::new(config.action_cache),
        false,
        "AC",
        &redis_backends,
        amberflo_backend.as_ref(),
    )
    .await?;
    let address: SocketAddr = config.listen_address.parse().unwrap();
    let server = Server::new(
        cas,
        action_cache,
        config.check_action_cache_completeness.unwrap_or_default(),
        config.completeness_check_probability.unwrap_or(1000),
    );

    let incoming = AddrIncoming::bind(&address).expect("failed to bind port");
    log::info!("Serving storage on {}", &address);

    // Setup infra endpoints.
    let in_flight_requests_counter = InFlightRequestsCounter::new();
    let in_flight_requests_counter_2 = in_flight_requests_counter.clone();
    let mut shutdown_receiver = setup_infra_endpoints(config.infra.unwrap_or_default(), move || {
        let count = in_flight_requests_counter_2.get();
         metrics::gauge!("toolchain_grpc_inflight_requests", count as f64, "service" => "storage_server");
        scrape_redis_backend_metrics(&redis_backends);
    })
    .expect("setup infra endpoints");
    server
        .serve_with_incoming_shutdown(
            AddrIncomingWithStream(incoming),
            async move { while shutdown_receiver.changed().await.is_ok() {} },
            config.grpc,
            in_flight_requests_counter,
        )
        .await?;

    Ok(())
}
