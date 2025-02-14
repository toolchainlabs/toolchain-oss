// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

#![deny(warnings)]
#![allow(clippy::new_without_default, clippy::len_without_is_empty)]

pub mod api;

mod bytes;
pub use digest::Digest;

pub mod driver;
pub mod uuid_gen;

#[allow(clippy::derive_partial_eq_without_eq)]
pub mod protos {
    pub mod toolchain {
        pub mod storage {
            pub mod redis {
                include!(concat!(env!("OUT_DIR"), "/toolchain.storage.redis.rs"));
            }
        }
    }
}

pub mod testutil;
