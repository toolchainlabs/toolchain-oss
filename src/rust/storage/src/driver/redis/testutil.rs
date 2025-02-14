// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::collections::VecDeque;
use std::sync::Arc;

use async_trait::async_trait;
use bytes::Bytes;
use futures::{future, FutureExt};
use parking_lot::Mutex;
use redis::aio::ConnectionLike;
use redis::{Cmd, ErrorKind as RedisErrorKind, Pipeline, RedisError, RedisFuture, Value};
use tryfuture::try_future;

use super::common::ConnectionGetter;
use super::traits::{IdentifyRedisConnection, RedisConnectionName};
use crate::driver::redis::traits::AsRedisConnectionMut;

/// Helper trait for converting test values into a `redis::Value` returned from a
/// `MockRedisConnection`. This is necessary because neither `redis::types::ToRedisArgs`
/// nor `redis::types::FromRedisValue` performs the precise conversion needed.
pub trait IntoRedisValue {
    fn into_redis_value(self) -> Value;
}

impl IntoRedisValue for String {
    fn into_redis_value(self) -> Value {
        Value::Data(self.as_bytes().to_vec())
    }
}

impl IntoRedisValue for &str {
    fn into_redis_value(self) -> Value {
        Value::Data(self.as_bytes().to_vec())
    }
}

impl IntoRedisValue for Bytes {
    fn into_redis_value(self) -> Value {
        Value::Data(self.to_vec())
    }
}

impl IntoRedisValue for Vec<u8> {
    fn into_redis_value(self) -> Value {
        Value::Data(self)
    }
}

impl IntoRedisValue for Value {
    fn into_redis_value(self) -> Value {
        self
    }
}

/// Helper trait for converting redis::Cmd and redis::Pipeline instances into
/// encoded byte vectors.
pub trait IntoRedisCmdBytes {
    fn into_redis_cmd_bytes(self) -> Vec<u8>;
}

impl IntoRedisCmdBytes for Cmd {
    fn into_redis_cmd_bytes(self) -> Vec<u8> {
        self.get_packed_command()
    }
}

impl IntoRedisCmdBytes for &Cmd {
    fn into_redis_cmd_bytes(self) -> Vec<u8> {
        self.get_packed_command()
    }
}

impl IntoRedisCmdBytes for &mut Cmd {
    fn into_redis_cmd_bytes(self) -> Vec<u8> {
        self.get_packed_command()
    }
}

impl IntoRedisCmdBytes for Pipeline {
    fn into_redis_cmd_bytes(self) -> Vec<u8> {
        self.get_packed_pipeline()
    }
}

impl IntoRedisCmdBytes for &mut Pipeline {
    fn into_redis_cmd_bytes(self) -> Vec<u8> {
        self.get_packed_pipeline()
    }
}

/// A single mock command to be expected by a test.
pub struct MockCommand {
    cmd_bytes: Vec<u8>,
    responses: Result<Vec<Value>, RedisError>,
}

impl MockCommand {
    /// Create a new `MockCommand` given a Redis command and either a value convertible to
    /// a `redis::Value` or a `RedisError`.
    pub fn new<C, V>(cmd: C, response: Result<V, RedisError>) -> Self
    where
        C: IntoRedisCmdBytes,
        V: IntoRedisValue,
    {
        MockCommand {
            cmd_bytes: cmd.into_redis_cmd_bytes(),
            responses: response.map(|r| vec![r.into_redis_value()]),
        }
    }

    /// Create a new `MockCommand` given a Redis command/pipeline and a vector of value convertible
    /// to a `redis::Value` or a `RedisError`.
    pub fn with_values<C, V>(cmd: C, responses: Result<Vec<V>, RedisError>) -> Self
    where
        C: IntoRedisCmdBytes,
        V: IntoRedisValue,
    {
        MockCommand {
            cmd_bytes: cmd.into_redis_cmd_bytes(),
            responses: responses.map(|xs| xs.into_iter().map(|x| x.into_redis_value()).collect()),
        }
    }
}

/// Fake Redis connection that checks whether the commands "sent" to it match the expected
/// list of mock commands provided.
#[derive(Clone)]
pub struct MockRedisConnection {
    commands: Arc<Mutex<VecDeque<MockCommand>>>,
}

impl MockRedisConnection {
    pub fn new(commands: Vec<MockCommand>) -> Self {
        MockRedisConnection {
            commands: Arc::new(Mutex::new(VecDeque::from(commands))),
        }
    }
}

impl ConnectionLike for MockRedisConnection {
    fn req_packed_command<'a>(&'a mut self, cmd: &'a Cmd) -> RedisFuture<'a, Value> {
        let mut commands = self.commands.lock();
        let packed_cmd = cmd.get_packed_command();
        let next_cmd = try_future!(commands.pop_front().ok_or_else(|| {
            RedisError::from((RedisErrorKind::ClientError, "unexpected command"))
        }));
        if packed_cmd != next_cmd.cmd_bytes {
            return future::ready(Err(RedisError::from((
                RedisErrorKind::ClientError,
                "unexpected command",
                format!(
                    "expected={}, got={}",
                    String::from_utf8(next_cmd.cmd_bytes)
                        .unwrap_or_else(|_| "decode error".to_owned()),
                    String::from_utf8(packed_cmd).unwrap_or_else(|_| "decode error".to_owned()),
                ),
            ))))
            .boxed();
        }
        let response = next_cmd.responses.map(|values| {
            // TODO: Properly return errors.
            // let value = try_future!(values.into_iter().next().ok_or_else(|| {
            //     RedisError::from((RedisErrorKind::ClientError, "bad mock command"))
            // }));

            values.into_iter().next().unwrap()
        });
        future::ready(response).boxed()
    }

    fn req_packed_commands<'a>(
        &'a mut self,
        cmd: &'a Pipeline,
        _offset: usize,
        _count: usize,
    ) -> RedisFuture<'a, Vec<Value>> {
        // TODO: This ignores `offset` and `count`.
        let mut commands = self.commands.lock();
        let packed_cmd = cmd.get_packed_pipeline();
        let next_cmd = try_future!(commands.pop_front().ok_or_else(|| {
            RedisError::from((RedisErrorKind::ClientError, "unexpected command"))
        }));
        if packed_cmd != next_cmd.cmd_bytes {
            return future::ready(Err(RedisError::from((
                RedisErrorKind::ClientError,
                "unexpected command",
                format!(
                    "expected={}, got={}",
                    String::from_utf8(next_cmd.cmd_bytes)
                        .unwrap_or_else(|_| "decode error".to_owned()),
                    String::from_utf8(packed_cmd).unwrap_or_else(|_| "decode error".to_owned()),
                ),
            ))))
            .boxed();
        }
        future::ready(next_cmd.responses).boxed()
    }

    fn get_db(&self) -> i64 {
        0
    }
}

#[async_trait]
impl ConnectionGetter for MockRedisConnection {
    type Connection = MockRedisConnection;

    async fn get_redis_connection(
        &self,
        _read_write: bool,
    ) -> Result<Self::Connection, RedisError> {
        Ok(self.clone())
    }

    async fn verify_connection(&self) -> Result<(), String> {
        Ok(())
    }
}

impl AsRedisConnectionMut for MockRedisConnection {
    type Target = Self;

    fn as_redis_conn_mut(&mut self) -> &mut Self::Target {
        self
    }
}

impl IdentifyRedisConnection for MockRedisConnection {
    fn identify_redis_connection(&self) -> RedisConnectionName {
        RedisConnectionName {
            backend: "test".into(),
            endpoint: "test",
        }
    }
}
