// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

mod chunked;
pub mod common;
mod direct;
pub mod pool;
pub(crate) mod traits;

#[cfg(test)]
mod testutil;

pub use chunked::RedisStorage;
pub use common::RedisBackend;
pub use direct::RedisDirectStorage;
pub use traits::{AsRedisConnectionMut, IdentifyRedisConnection, RedisConnectionName};
