// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

fn main() -> Result<(), Box<dyn std::error::Error>> {
    prost_build::compile_protos(&["protos/redis.proto"], &["protos/"])?;
    Ok(())
}
