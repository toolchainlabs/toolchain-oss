#!/bin/bash
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euxo pipefail

echo "Build rust target $1"
cargo build --release --locked --manifest-path="$1/Cargo.toml" --target-dir=./target && cp "target/release/$1" /toolchain/host_repo/dist/