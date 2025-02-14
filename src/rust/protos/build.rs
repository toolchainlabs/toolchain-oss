// Copyright 2020 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut config = prost_build::Config::new();
    config.bytes(["."]);
    config.disable_comments(["."]);

    tonic_build::configure()
    .build_client(true)
    .build_server(true)
    .compile_with_config(
        config,
      &[
        "protos/bazelbuild_remote-apis/build/bazel/remote/execution/v2/remote_execution.proto",
        "protos/bazelbuild_remote-apis/build/bazel/semver/semver.proto",
        "protos/googleapis/google/bytestream/bytestream.proto",
        "protos/googleapis/google/devtools/remoteworkers/v1test2/bots.proto",
        "protos/googleapis/google/devtools/remoteworkers/v1test2/command.proto",
        "protos/googleapis/google/devtools/remoteworkers/v1test2/worker.proto",
        "protos/googleapis/google/rpc/code.proto",
        "protos/googleapis/google/rpc/error_details.proto",
        "protos/googleapis/google/rpc/status.proto",
        "protos/googleapis/google/longrunning/operations.proto",
        "protos/standard/google/protobuf/empty.proto",
      ],
      &[
        "protos/bazelbuild_remote-apis",
        "protos/googleapis",
        "protos/standard",
      ],
    )?;

    Ok(())
}
