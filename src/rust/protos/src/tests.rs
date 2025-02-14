// Copyright 2020 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use bytes::BytesMut;
use prost::Message;

use crate::build::bazel::remote::execution::v2 as reapi_protos;

#[test]
fn test_remote_execution_protos() {
    let mut command = reapi_protos::Command::default();
    command.arguments = vec![
        String::from("/bin/sh"),
        String::from("-c"),
        String::from("ls"),
    ];

    let mut command_bytes = BytesMut::with_capacity(command.encoded_len());
    command.encode(&mut command_bytes).unwrap();

    let command2 = reapi_protos::Command::decode(&mut command_bytes).expect("decoded command");

    assert_eq!(command, command2);
}
