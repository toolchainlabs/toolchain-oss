// Copyright 2022 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

//! Async Redis connection pool
//!
//! This module implements an asynchronous Redis connection pool. Unlike the ConnectionManager
//! and MultiplexedConnection from the `redis` crate, this module provides a pool that uses
//! multiple tasks to drive N connections to Redis without having to put a connection in and out
//! of a traditional connection pool under a lock. Moreover, it avoids the PING commands sent
//! by `deadpool-redis` on every recycle of a connection between requests.

use std::time::Instant;

use async_channel::{Receiver, Sender};
use async_trait::async_trait;
use grpc_util::retry::retry_call;
use redis::aio::ConnectionLike;
use redis::{Cmd, ErrorKind, Pipeline, RedisError, RedisFuture, RedisResult, Value as RedisValue};
use tokio::sync::oneshot::Sender as OneshotSender;

use crate::driver::redis::common::{send_info_cmd, ConnectionGetter};
use crate::driver::redis::traits::{
    AsRedisConnectionMut, IdentifyRedisConnection, RedisConnectionName,
};

/// Async Redis connection pool
///
/// This is an async-first connection pool that will drive N connections to Redis. It exposes
/// the same `redis::aio::ConnectionLike` interface as other Redis clients in the redis crate,
/// but will multiplex requests over the N managed connections.
#[derive(Clone)]
pub struct AsyncRedisConnectionPool {
    requests_sender: Sender<RedisRequest>,
    conn_name: String,
    conn_endpoint: &'static str,
}

enum RedisRequestCmd {
    Single(Vec<u8>),
    Pipeline {
        pipeline_packed: Vec<u8>,
        count: usize,
        offset: usize,
    },
}

enum RedisResponse {
    Single(RedisResult<RedisValue>),
    Pipeline(RedisResult<Vec<RedisValue>>),
}

/// A single Redis request made to the async client. Responses will be sent to the caller
/// via the one-shot channel included in the request.
struct RedisRequest {
    /// The Redis command to run
    cmd: RedisRequestCmd,

    /// TIme when this request was created. Used to track queueing times.
    creation_time: Instant,

    /// One-shot channel that receives the response
    response_sender: OneshotSender<RedisResponse>,
}

/// Returns true if the result is an connection error.
fn check_for_conn_error<T>(result: &RedisResult<T>) -> bool {
    match result {
        Ok(_) => false,
        Err(err) => err.is_connection_dropped() || err.is_connection_refusal(),
    }
}

enum EventLoopStepResult {
    Ok,
    ChannelRecvErr,
    Disconnected,
}

/// Evaluate a single step of the event loop.
async fn redis_event_loop_step<C>(
    conn: &mut C,
    requests_receiver: &Receiver<RedisRequest>,
    conn_name: String,
    conn_endpoint: &'static str,
) -> EventLoopStepResult
where
    C: ConnectionLike,
{
    let request = match requests_receiver.recv().await {
        Ok(r) => r,
        Err(_) => return EventLoopStepResult::ChannelRecvErr,
    };

    let start_time = Instant::now();

    let queued_duration = start_time.duration_since(request.creation_time);

    metrics::histogram!(
        "toolchain_storage_redis_request_queued_duration_seconds",
        queued_duration,
        "redis_backend" => conn_name.to_string(),
        "redis_endpoint" => conn_endpoint,
    );

    // Check whether the request has already been cancelled, and if so, don't execute it.
    if request.response_sender.is_closed() {
        metrics::counter!(
            "toolchain_storage_redis_request_cancelled",
            1,
            "redis_backend" => conn_name.to_string(),
            "redis_endpoint" => conn_endpoint,
        );
        return EventLoopStepResult::Ok;
    }

    let (elapsed, is_connection_dropped) = match request.cmd {
        RedisRequestCmd::Single(cmd_bytes) => {
            let cmd = Cmd::with_packed_data(cmd_bytes);
            let redis_result = conn.req_packed_command(&cmd).await;
            let elapsed = start_time.elapsed();
            let is_connection_dropped = check_for_conn_error(&redis_result);
            if request
                .response_sender
                .send(RedisResponse::Single(redis_result))
                .is_err()
            {
                metrics::counter!(
                    "toolchain_storage_redis_request_cancelled",
                    1,
                    "redis_backend" => conn_name.to_string(),
                    "redis_endpoint" => conn_endpoint,
                );
            }
            (elapsed, is_connection_dropped)
        }
        RedisRequestCmd::Pipeline {
            pipeline_packed,
            count,
            offset,
        } => {
            let pipeline = Pipeline::with_packed_data(pipeline_packed);
            let redis_result = conn.req_packed_commands(&pipeline, offset, count).await;
            let elapsed = start_time.elapsed();
            let is_connection_dropped = check_for_conn_error(&redis_result);
            if request
                .response_sender
                .send(RedisResponse::Pipeline(redis_result))
                .is_err()
            {
                metrics::counter!(
                    "toolchain_storage_redis_request_cancelled",
                    1,
                    "redis_backend" => conn_name.to_string(),
                    "redis_endpoint" => conn_endpoint,
                );
            }
            (elapsed, is_connection_dropped)
        }
    };

    metrics::histogram!(
        "toolchain_storage_redis_requests_duration_seconds",
        elapsed,
        "redis_backend" => conn_name.clone(),
        "redis_endpoint" => conn_endpoint,
    );
    if is_connection_dropped {
        EventLoopStepResult::Disconnected
    } else {
        EventLoopStepResult::Ok
    }
}

/// Drives a single connection to Redis.
async fn redis_connection_task<CG>(
    conn_getter: CG,
    requests_receiver: Receiver<RedisRequest>,
    conn_name: String,
    conn_endpoint: &'static str,
) -> Result<(), RedisError>
where
    CG: ConnectionGetter + Clone + Send + Sync + 'static,
{
    'CONN: loop {
        // Connect to Redis.
        let mut conn = match retry_call(
            conn_getter.clone(),
            |conn_getter| async move { conn_getter.get_redis_connection(true).await },
            |err| {
                metrics::counter!(
                    "toolchain_storage_redis_connect_failed_total",
                    1,
                    "redis_backend" => conn_name.clone(),
                    "redis_endpoint" => conn_endpoint,
                );
                log::error!("Failed to connect to Redis: {}", err);
                true
            },
        )
        .await
        {
            Ok(conn) => conn,
            Err(err) => {
                log::error!(
                    "Failed to connect to Redis after multiple retries: {err}. Will continue to retry."
                );
                continue 'CONN;
            }
        };
        let conn = conn.as_redis_conn_mut();

        loop {
            match redis_event_loop_step(conn, &requests_receiver, conn_name.clone(), conn_endpoint)
                .await
            {
                EventLoopStepResult::Ok => (),
                EventLoopStepResult::Disconnected => {
                    log::debug!(
                        "Redis disconnected: conn_name={}, conn_endpoint={}",
                        &conn_name,
                        conn_endpoint
                    );

                    metrics::counter!(
                        "toolchain_storage_redis_disconnected_total",
                        1,
                        "redis_backend" => conn_name.clone(),
                        "redis_endpoint" => conn_endpoint,
                    );
                    continue 'CONN;
                }
                EventLoopStepResult::ChannelRecvErr => return Ok(()),
            }
        }
    }
}

impl AsyncRedisConnectionPool {
    pub fn new<CG>(
        conn_getter: CG,
        num_connections: usize,
        conn_name: String,
        conn_endpoint: &'static str,
    ) -> Self
    where
        CG: ConnectionGetter + Clone + Send + Sync + 'static,
    {
        let (requests_sender, requests_receiver) = async_channel::bounded(3 * num_connections);

        for i in 0..num_connections {
            let conn_getter2 = conn_getter.clone();
            let requests_receiver2 = requests_receiver.clone();
            let conn_name2 = conn_name.clone();
            tokio::spawn(async move {
                let result = redis_connection_task(
                    conn_getter2,
                    requests_receiver2,
                    conn_name2,
                    conn_endpoint,
                )
                .await;
                if let Err(err) = &result {
                    log::error!("redis_connection_task #{i} exited with error: {err}");
                }
            });
        }

        Self {
            requests_sender,
            conn_name,
            conn_endpoint,
        }
    }
}

#[async_trait]
impl ConnectionGetter for AsyncRedisConnectionPool {
    type Connection = Self;

    async fn get_redis_connection(
        &self,
        _read_write: bool,
    ) -> Result<Self::Connection, RedisError> {
        Ok(self.clone())
    }

    async fn verify_connection(&self) -> Result<(), String> {
        let mut conn = self
            .get_redis_connection(false)
            .await
            .map_err(|err| format!("Redis error: {err}"))?;
        send_info_cmd(conn.as_redis_conn_mut(), "async-redis")
            .await
            .map_err(|err| format!("Redis error: {err}"))
    }
}

impl ConnectionLike for AsyncRedisConnectionPool {
    fn req_packed_command<'a>(&'a mut self, cmd: &'a Cmd) -> RedisFuture<'a, RedisValue> {
        let redis_cmd_bytes = cmd.get_packed_command();
        let (response_sender, response_receiver) = tokio::sync::oneshot::channel();
        let request_sender = self.requests_sender.clone();

        Box::pin(async move {
            let redis_request = RedisRequest {
                cmd: RedisRequestCmd::Single(redis_cmd_bytes),
                creation_time: Instant::now(),
                response_sender,
            };
            request_sender.send(redis_request).await.map_err(|_| {
                RedisError::from((ErrorKind::ClientError, "internal driver error - send"))
            })?;
            let response = response_receiver.await.map_err(|_| {
                RedisError::from((ErrorKind::ClientError, "internal driver error - recv"))
            })?;
            match response {
                RedisResponse::Single(result) => result,
                _ => Err(RedisError::from((
                    ErrorKind::ClientError,
                    "internal driver error - unexpected response type",
                ))),
            }
        })
    }

    fn req_packed_commands<'a>(
        &'a mut self,
        pipeline: &'a Pipeline,
        offset: usize,
        count: usize,
    ) -> RedisFuture<'a, Vec<RedisValue>> {
        let redis_pipeline_bytes = pipeline.get_packed_pipeline();
        let (response_sender, response_receiver) = tokio::sync::oneshot::channel();
        let request_sender = self.requests_sender.clone();

        Box::pin(async move {
            let redis_request = RedisRequest {
                cmd: RedisRequestCmd::Pipeline {
                    pipeline_packed: redis_pipeline_bytes,
                    count,
                    offset,
                },
                creation_time: Instant::now(),
                response_sender,
            };
            request_sender.send(redis_request).await.map_err(|_| {
                RedisError::from((ErrorKind::ClientError, "internal stream error - send"))
            })?;
            let response = response_receiver.await.map_err(|_| {
                RedisError::from((ErrorKind::ClientError, "internal stream error - recv"))
            })?;
            match response {
                RedisResponse::Pipeline(result) => result,
                _ => Err(RedisError::from((
                    ErrorKind::ClientError,
                    "internal driver error - unexpected response type",
                ))),
            }
        })
    }

    fn get_db(&self) -> i64 {
        // Default to Redis database 0 since our Redis cluster does not use multiple databases.
        0
    }
}

impl AsRedisConnectionMut for AsyncRedisConnectionPool {
    type Target = Self;

    #[inline]
    fn as_redis_conn_mut(&mut self) -> &mut Self::Target {
        self
    }
}

impl IdentifyRedisConnection for AsyncRedisConnectionPool {
    fn identify_redis_connection(&self) -> RedisConnectionName {
        RedisConnectionName {
            backend: self.conn_name.clone(),
            endpoint: self.conn_endpoint,
        }
    }
}

#[cfg(test)]
mod tests {
    use redis::Cmd;

    use crate::driver::redis::pool::AsyncRedisConnectionPool;
    use crate::driver::redis::testutil::{MockCommand, MockRedisConnection};

    fn exists_cmd(key: impl AsRef<str>) -> Cmd {
        let mut cmd = redis::cmd("EXISTS");
        cmd.arg(key.as_ref());
        cmd
    }

    #[tokio::test]
    async fn basic_async_pool_end_to_end() {
        let conn = MockRedisConnection::new(vec![MockCommand::new(exists_cmd("xyzzy"), Ok("1"))]);

        let mut pool = AsyncRedisConnectionPool::new(conn, 1, "test".to_string(), "test");

        let result: bool = exists_cmd("xyzzy").query_async(&mut pool).await.unwrap();
        assert!(result);
    }
}
