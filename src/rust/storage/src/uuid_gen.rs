// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use rand::Rng;
use uuid::Uuid;

/// Generates a new UUID. Abstracted as a trait to allow overriding in tests.
pub trait UuidGenerator {
    fn generate_uuid(&self) -> String;
}

/// Generate a random UUID. Unlike `Uuid::new_v4` which uses the `getrandom` crate, this uses
/// the `rand` crate including its thread-local RNG. The `getrandom` crate always tries to use
/// the kernel's RNG which is not as flexible as using the `rand` crate's RNGs. (The
/// `getrandom` docs actually recommend using `rand`!)
pub struct DefaultUuidGenerator;

impl UuidGenerator for DefaultUuidGenerator {
    fn generate_uuid(&self) -> String {
        let mut rng = rand::thread_rng();
        let bytes: [u8; 16] = rng.gen();
        Uuid::from_slice(&bytes).unwrap().to_string()
    }
}
