// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use rand::Rng;
use uuid::Uuid;

pub type OperationName = String;

pub type InstanceName = String;

pub type SessionName = String;

/// NB: See `storage/src/uuid_gen.rs` for the reason for using `rand::thread_rng` here.
pub fn generate_uuid() -> String {
    let mut rng = rand::thread_rng();
    Uuid::from_bytes(rng.gen()).to_string()
}

pub fn generate_session_name(instance_name: &InstanceName) -> SessionName {
    format!("{instance_name}/{}", generate_uuid())
}

pub fn generate_operation_name(instance_name: &InstanceName) -> OperationName {
    format!("{instance_name}/{}", generate_uuid())
}

pub fn instance_name_from_operation_name(name: &OperationName) -> Result<InstanceName, String> {
    let (instance_name, _) = name
        .split_once('/')
        .ok_or_else(|| format!("unable to parse instance from `{name}`"))?;
    Ok(instance_name.to_owned())
}

pub fn instance_name_from_session_name(name: &SessionName) -> Result<InstanceName, String> {
    let (instance_name, _) = name
        .split_once('/')
        .ok_or_else(|| format!("unable to parse instance from `{name}`"))?;
    Ok(instance_name.to_owned())
}
