// Copyright 2022 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use crate::driver::{DriverState, Instance, SmallBlobStorage, StorageError};
use crate::Digest;
use async_trait::async_trait;
use bytes::Bytes;

/// Null storage driver that accepts (but does not store) all writes and returns missing
/// for all reads.
pub struct AlwaysErrorsStorage;

#[async_trait]
impl SmallBlobStorage for AlwaysErrorsStorage {
    async fn find_missing_blobs(
        &self,
        _instance: Instance,
        _digests: Vec<Digest>,
        _state: DriverState,
    ) -> Result<Vec<Digest>, StorageError> {
        Err(StorageError::Internal(
            "This always will error!".to_string(),
        ))
    }

    async fn read_blob(
        &self,
        _instance: Instance,
        _digest: Digest,
        _state: DriverState,
    ) -> Result<Option<Bytes>, StorageError> {
        Err(StorageError::Internal(
            "This always will error!".to_string(),
        ))
    }

    async fn write_blob(
        &self,
        _instance: Instance,
        _digest: Digest,
        _content: Bytes,
        _state: DriverState,
    ) -> Result<(), StorageError> {
        Err(StorageError::Internal(
            "This always will error!".to_string(),
        ))
    }
}
