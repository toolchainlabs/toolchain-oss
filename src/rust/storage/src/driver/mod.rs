// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::pin::Pin;

use async_trait::async_trait;
use bytes::Bytes;
use digest::Digest;
use futures::Stream;

mod always_errors;
mod chunking;
mod dark_launch;
mod digest_verifier;
mod error;
mod existence_cache;
mod fast_slow;
mod file_backed;
mod memory;
mod metering;
mod metrics;
mod null;
pub mod redis;
mod sharding;
mod size_split;
mod small;

pub use self::metering::{AmberfloEmitter, MeteredStorage};
pub use self::metrics::MetricsMonitoredStorage;
pub use self::redis::{RedisBackend, RedisDirectStorage, RedisStorage};
pub use always_errors::AlwaysErrorsStorage;
pub use chunking::ChunkingStorage;
pub use dark_launch::DarkLaunchStorage;
pub use digest_verifier::{ReadDigestVerifier, WriteDigestVerifier};
pub use error::{StorageError, StreamingWriteError};
pub use existence_cache::ExistenceCacheStorage;
pub use fast_slow::FastSlowReplicationStorage;
pub use file_backed::FileBackedStorage;
pub use memory::{MemoryStorage, MemoryWriteAttempt};
pub use null::NullStorage;
pub use sharding::ShardingStorage;
pub use size_split::SizeSplitStorage;
pub use small::{BlobStorageAdapter, SmallBlobStorage, SmallBlobStorageAdapter};

/// A mechanism to pass state to other drivers.
///
/// The type may be cloned many times, rather than sharing the same instance for the whole binary
/// via `Arc`. This implies that state is passed down one-way, from caller to callee
/// (like props in React). It always starts empty from the `api/` callers, meaning that
/// state is only ever added by other drivers.
///
/// Example use case: a driver can set the field `is_sharded` to `true`, and then the sharding
/// driver can check to know whether to no-op or keep sharding.
///
/// Driver authors can add new fields and methods when they would like to use some new state.
#[derive(Clone, Debug, Default)]
pub struct DriverState;

/// Represents metadata about an REAPI instance. Only stores a `name` for now.
#[derive(Clone, Hash, Eq, PartialEq)]
pub struct Instance {
    pub name: String, // TODO: should only hash on name if more attributes added
}

impl<T: AsRef<str>> From<T> for Instance {
    fn from(name: T) -> Self {
        Self {
            name: name.as_ref().to_string(),
        }
    }
}

/// Represents temporary resources in the driver for writing blobs. The API layer uses this
/// trait to commit an upload only when the API layer's success criteria for an upload have
/// been met.
///
/// If the `WriteAttempt` is dropped by the API layer without calling `commit`, then the driver
/// should destroy resources associated with the upload and not make the upload visible. For
/// example, an upload could have content that does not match the digest or another caller could
/// have uploaded the same digest concurrently and finished first.
#[async_trait]
pub trait WriteAttemptOps {
    /// Write a `Bytes` into the blob.
    async fn write(&mut self, batch: Bytes) -> Result<(), StreamingWriteError>;

    /// Consumes the `WriteAttempt` and commits the blob to storage. After this call, the blob must
    /// be visible to a call to BlobStorage::read_blob.
    ///
    /// Note: There may be multiple writes for the same `Digest` occurring concurrently. The
    /// driver must handle its own coordination in accessing storage.
    async fn commit(self: Box<Self>) -> Result<(), StreamingWriteError>;
}

/// Alias for the type of a read stream.
pub type BoxReadStream = Pin<Box<dyn Stream<Item = Result<Bytes, StorageError>> + Send + 'static>>;

/// Represents how to read and write blobs by digest into the storage managed by the driver.
/// These methods are designed to operate asynchronously and in a way that matches the piecemeal
/// basis for reads and writes inherent in the Google ByteStream API.
#[async_trait]
pub trait BlobStorage {
    /// Given a list of digests, return the digests that are **not** stored by this driver.
    ///
    /// This is used to implement the FindMissingBlobs RPC from the CAS API.
    async fn find_missing_blobs(
        &self,
        instance: Instance,
        digests: Vec<Digest>,
        state: DriverState,
    ) -> Result<Vec<Digest>, StorageError>;

    /// Return a stream of the bytes comprising the content of the `digest`. Using a stream allows
    /// a driver to return the content in a piecemeal fashion. The driver must return the content
    /// starting at `read_offset` and only up to `read_limit` bytes from that offset.
    ///
    /// TODO: Does it make sense to emulate `read_offset` at the API layer? Needs research into
    /// whether there are some drivers that cannot implement it easily. If so, extend
    /// this trait with capability methods (e.g., `accepts_read_offset`).
    async fn read_blob(
        &self,
        instance: Instance,
        digest: Digest,
        max_batch_size: usize,
        read_offset: Option<usize>, // default is read from beginning
        read_limit: Option<usize>,  // default is to return the entire blob
        state: DriverState,
    ) -> Result<Option<BoxReadStream>, StorageError>;

    /// Begin storing an upload into temporary upload space. The content for the blob will be
    /// streamed on a (potentially) piecemeal basis via `content_stream`.
    ///
    /// The API layer manages tracking UUIDs sent by the client and resumption of interrupted
    /// writes.
    async fn begin_write_blob(
        &self,
        instance: Instance,
        digest: Digest,
        state: DriverState,
    ) -> Result<Box<dyn WriteAttemptOps + Send + Sync + 'static>, StreamingWriteError>;

    /// Ensure the driver is setup to receive instances with the name `instance`.
    fn ensure_instance(&mut self, _instance: &Instance, _state: DriverState) {}
}

#[async_trait]
impl<BS> BlobStorage for Box<BS>
where
    BS: BlobStorage + Send + Sync + 'static + ?Sized,
{
    async fn find_missing_blobs(
        &self,
        instance: Instance,
        digests: Vec<Digest>,
        state: DriverState,
    ) -> Result<Vec<Digest>, StorageError> {
        (**self).find_missing_blobs(instance, digests, state).await
    }

    async fn read_blob(
        &self,
        instance: Instance,
        digest: Digest,
        max_batch_size: usize,
        read_offset: Option<usize>,
        read_limit: Option<usize>,
        state: DriverState,
    ) -> Result<Option<BoxReadStream>, StorageError> {
        (**self)
            .read_blob(
                instance,
                digest,
                max_batch_size,
                read_offset,
                read_limit,
                state,
            )
            .await
    }

    async fn begin_write_blob(
        &self,
        instance: Instance,
        digest: Digest,
        state: DriverState,
    ) -> Result<Box<dyn WriteAttemptOps + Send + Sync + 'static>, StreamingWriteError> {
        (**self).begin_write_blob(instance, digest, state).await
    }

    fn ensure_instance(&mut self, instance: &Instance, state: DriverState) {
        (**self).ensure_instance(instance, state)
    }
}

#[async_trait]
impl<WA> WriteAttemptOps for Box<WA>
where
    WA: WriteAttemptOps + Send + Sync + 'static,
{
    async fn write(&mut self, batch: Bytes) -> Result<(), StreamingWriteError> {
        (**self).write(batch).await
    }

    async fn commit(self: Box<Self>) -> Result<(), StreamingWriteError> {
        self.commit().await
    }
}
