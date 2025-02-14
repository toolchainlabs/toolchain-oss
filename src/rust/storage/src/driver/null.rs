// Copyright 2022 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use crate::driver::{DriverState, Instance, SmallBlobStorage, StorageError};
use crate::Digest;
use async_trait::async_trait;
use bytes::Bytes;

/// Null storage driver that accepts (but does not store) all writes and returns missing
/// for all reads.
pub struct NullStorage;

#[async_trait]
impl SmallBlobStorage for NullStorage {
    async fn find_missing_blobs(
        &self,
        _instance: Instance,
        digests: Vec<Digest>,
        _state: DriverState,
    ) -> Result<Vec<Digest>, StorageError> {
        Ok(digests)
    }

    async fn read_blob(
        &self,
        _instance: Instance,
        _digest: Digest,
        _state: DriverState,
    ) -> Result<Option<Bytes>, StorageError> {
        Ok(None)
    }

    async fn write_blob(
        &self,
        _instance: Instance,
        _digest: Digest,
        _content: Bytes,
        _state: DriverState,
    ) -> Result<(), StorageError> {
        Ok(())
    }
}
