// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

/// Converts a type into a redis::aio::ConnectionLike
///
/// Necessary to work around the orphan type rule since `deadpool::managed::Object` and
/// `redis::aio::ConnectionLike` are not in this crate and we want to implement
/// `redis::aio::ConnectionLike` for `deadpool::managed::Object` (although indirectly in this
/// case).
pub trait AsRedisConnectionMut {
    type Target: redis::aio::ConnectionLike + Send + 'static;

    /// Obtain a mutable reference to a `redis::aio::ConnectionLike` from this type.
    fn as_redis_conn_mut(&mut self) -> &mut Self::Target;
}

impl AsRedisConnectionMut for redis::aio::Connection {
    type Target = Self;

    #[inline]
    fn as_redis_conn_mut(&mut self) -> &mut Self::Target {
        self
    }
}

/// The name of a Redis connection. Used for logging data about a Redis connection.
#[derive(Clone, Debug)]
pub struct RedisConnectionName {
    /// The name of the backend.
    pub backend: String,

    /// The name of the endpoint of that backend used for this connection.
    pub endpoint: &'static str,
}

/// Retrieve a connection identifier from a Redis connection type.
pub trait IdentifyRedisConnection {
    fn identify_redis_connection(&self) -> RedisConnectionName;
}
