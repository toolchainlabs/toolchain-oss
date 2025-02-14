// Copyright 2022 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use async_trait::async_trait;
use bytes::{Bytes, BytesMut};
use futures::{StreamExt, TryFutureExt};

use crate::driver::{
    BlobStorage, DriverState, Instance, SmallBlobStorage, StorageError, StreamingWriteError,
};
use crate::Digest;

/// A `BlobStorage` that tries to read first from a "fast" storage (which is potentially
/// ephemeral), falling back to a "slow" but persistent storage if the "fast" storage did not have
/// the blob.
///
/// This is useful for putting an ephemeral cache in front of a slower persistent storage.
#[derive(Clone)]
pub struct FastSlowReplicationStorage<Fast, Slow> {
    fast_storage: Fast,
    slow_storage: Slow,
}

#[async_trait]
impl<Fast, Slow> SmallBlobStorage for FastSlowReplicationStorage<Fast, Slow>
where
    Fast: SmallBlobStorage + Send + Sync + 'static,
    Slow: BlobStorage + Send + Sync + 'static,
{
    async fn find_missing_blobs(
        &self,
        instance: Instance,
        digests: Vec<Digest>,
        state: DriverState,
    ) -> Result<Vec<Digest>, StorageError> {
        let digests_missing_from_fast = self
            .fast_storage
            .find_missing_blobs(instance.clone(), digests, state.clone())
            .await?;
        let missing_digests = self
            .slow_storage
            .find_missing_blobs(instance, digests_missing_from_fast, state)
            .await?;
        Ok(missing_digests)
    }

    async fn read_blob(
        &self,
        instance: Instance,
        digest: Digest,
        state: DriverState,
    ) -> Result<Option<Bytes>, StorageError> {
        // Check whether the fast storage has the blob.
        match self
            .fast_storage
            .read_blob(instance.clone(), digest, state.clone())
            .await
        {
            Ok(Some(content)) => return Ok(Some(content)),
            Ok(None) => (),
            Err(err) => {
                log::error!("Fast storage returned error: {}", err);
                // TODO: increment metric
            }
        }

        // If missing or on error, query the slow storage for the blob.
        let slow_stream = self
            .slow_storage
            .read_blob(
                instance.clone(),
                digest,
                128 * 1024 * 1024,
                None,
                None,
                state.clone(),
            )
            .await?;

        let mut slow_stream = match slow_stream {
            Some(s) => s,
            None => return Ok(None),
        };

        let mut buffer = BytesMut::with_capacity(digest.size_bytes);
        while let Some(chunk) = slow_stream.next().await {
            let chunk = chunk?;
            if (buffer.capacity() - buffer.len()) < chunk.len() {
                buffer.reserve(chunk.len());
            }
            buffer.extend_from_slice(&chunk[..]);
        }
        let content = buffer.freeze();

        self.fast_storage
            .write_blob(instance, digest, content.clone(), state)
            .await?;
        Ok(Some(content))
    }

    async fn write_blob(
        &self,
        instance: Instance,
        digest: Digest,
        content: Bytes,
        state: DriverState,
    ) -> Result<(), StorageError> {
        // The fast storage cannot complete early with a `StreamingWriteError::AlreadyExists`: only
        // the slow storage can. So we only exit early if the slow storage already has the blob.
        let fast_write = self
            .fast_storage
            .write_blob(instance.clone(), digest, content.clone(), state.clone())
            .map_err(StreamingWriteError::StorageError);
        let slow_write = async move {
            let mut attempt = self
                .slow_storage
                .begin_write_blob(instance, digest, state)
                .await?;
            attempt.write(content).await?;
            attempt.commit().await?;
            Ok(())
        };
        futures::try_join!(fast_write, slow_write)
            .map(|((), ())| ())
            .or_else(StreamingWriteError::ok_if_already_exists)
    }
}

impl<Fast, Slow> FastSlowReplicationStorage<Fast, Slow>
where
    Fast: SmallBlobStorage + Send + Sync + 'static,
    Slow: BlobStorage + Send + Sync + 'static,
{
    /// Create a new `FastSlowReplicationStorage` with the given storage drivers for the
    /// "fast" and "slow" backends.
    pub fn new(fast_storage: Fast, slow_storage: Slow) -> Self {
        Self {
            fast_storage,
            slow_storage,
        }
    }

    /// Consume this `BlobStorage` and return the child fast/slow storage implementations.
    #[cfg(test)]
    pub fn into_inner(self) -> (Fast, Slow) {
        (self.fast_storage, self.slow_storage)
    }

    #[cfg(test)]
    pub fn get_ref(&self) -> (&Fast, &Slow) {
        (&self.fast_storage, &self.slow_storage)
    }
}

#[cfg(test)]
mod tests {
    use std::sync::Arc;
    use std::time::Duration;

    use bytes::Bytes;

    use super::FastSlowReplicationStorage;
    use crate::driver::{
        BlobStorage, DriverState, Instance, MemoryStorage, SmallBlobStorage, StreamingWriteError,
    };
    use crate::testutil::{
        AlwaysExistsStorage, CountMethodCallsStorage, SmallMemoryStorage, TestData,
        WriteSemaphoreOperation, WriteSemaphoreStorage,
    };
    use crate::Digest;

    async fn write_blob<BS>(
        storage: &BS,
        instance: Instance,
        digest: Digest,
        content: Bytes,
    ) -> Result<(), StreamingWriteError>
    where
        BS: BlobStorage + Send + Sync + 'static,
    {
        let mut attempt = storage
            .begin_write_blob(instance, digest, DriverState::default())
            .await?;
        attempt.write(content).await?;
        attempt.commit().await
    }

    #[tokio::test]
    async fn fast_slow_basic_operations() {
        let instance = Instance::from("main");
        let content1 = TestData::from_static(b"foobar");
        let content2 = TestData::from_static(b"foobarxyzzy");

        let fast_write_semaphore = Arc::new(tokio::sync::Semaphore::new(0));
        let fast_storage = CountMethodCallsStorage::new(WriteSemaphoreStorage::new(
            SmallMemoryStorage::new(),
            fast_write_semaphore.clone(),
        ));
        fast_storage
            .write_blob(
                instance.clone(),
                content1.digest,
                content1.bytes.clone(),
                DriverState::default(),
            )
            .await
            .unwrap();

        let mut slow_storage = CountMethodCallsStorage::new(MemoryStorage::new());
        slow_storage.ensure_instance(&instance, DriverState::default());
        write_blob(
            &slow_storage,
            instance.clone(),
            content2.digest,
            content2.bytes.clone(),
        )
        .await
        .unwrap();

        let storage = FastSlowReplicationStorage::new(fast_storage, slow_storage);

        // Both digests should be present.
        let missing_blobs = storage
            .find_missing_blobs(
                instance.clone(),
                vec![content1.digest, content2.digest],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert!(missing_blobs.is_empty());
        {
            let (fast_storage, slow_storage) = storage.get_ref();
            assert_eq!(fast_storage.counts(), (1, 0, 1));
            assert_eq!(slow_storage.counts(), (1, 0, 1));
        }

        // Reading the first digest (which is only in the fast storage) should succeed and no
        // access of the slow storage should occur.
        let actual_content1 = storage
            .read_blob(instance.clone(), content1.digest, DriverState::default())
            .await
            .unwrap()
            .unwrap();
        assert_eq!(content1.bytes, actual_content1);
        {
            let (fast_storage, slow_storage) = storage.get_ref();
            assert_eq!(fast_storage.counts(), (1, 1, 1));
            assert_eq!(slow_storage.counts(), (1, 0, 1));
        }

        // Reading the second digest (which is only in the slow storage) should succeed and
        // result in the digest being written into the fast storage as well (verified by
        // splitting the fast/slow storage and querying each storage individually).
        let actual_content2 = storage
            .read_blob(instance.clone(), content2.digest, DriverState::default())
            .await
            .unwrap()
            .unwrap();
        assert_eq!(content2.bytes, actual_content2);

        // Wait for the write to complete.
        let permits =
            tokio::time::timeout(Duration::from_secs(1), fast_write_semaphore.acquire_many(2))
                .await
                .unwrap()
                .unwrap();
        permits.forget();

        {
            let (fast_storage, slow_storage) = storage.get_ref();
            assert_eq!(fast_storage.counts(), (1, 2, 2));
            assert_eq!(slow_storage.counts(), (1, 1, 1));
        }

        let (fast_storage, slow_storage) = storage.into_inner();
        let missing_blobs = fast_storage
            .find_missing_blobs(
                instance.clone(),
                vec![content1.digest, content2.digest],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert!(missing_blobs.is_empty());

        // Put the fast/slow storage back together for write test.
        let storage = FastSlowReplicationStorage::new(fast_storage, slow_storage);

        let content3 = TestData::from_static(b"helloworld");

        // Writing a blob that has never been seen should result in both fast and slow storage
        // drivers receiving the blob.
        storage
            .write_blob(
                instance.clone(),
                content3.digest,
                content3.bytes.clone(),
                DriverState::default(),
            )
            .await
            .unwrap();

        let (fast_storage, slow_storage) = storage.into_inner();
        let missing_blobs = fast_storage
            .find_missing_blobs(
                instance.clone(),
                vec![content3.digest],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert!(missing_blobs.is_empty());

        let missing_blobs = slow_storage
            .find_missing_blobs(
                instance.clone(),
                vec![content3.digest],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert!(missing_blobs.is_empty());
    }

    #[tokio::test]
    async fn existing_blob_slow() {
        let instance = Instance::from("main");
        let content1 = TestData::from_static(b"foobar");

        // Use a fast storage instance which will never successfully complete the write.
        let fast_write_semaphore = Arc::new(tokio::sync::Semaphore::new(0));
        let fast_storage = WriteSemaphoreStorage::with_operation(
            SmallMemoryStorage::new(),
            fast_write_semaphore.clone(),
            WriteSemaphoreOperation::Acquire,
        );
        let slow_storage = AlwaysExistsStorage;

        let storage = FastSlowReplicationStorage::new(fast_storage, slow_storage);

        // Writing a blob that the slow storage claims to already be holding should exit early,
        // even though the fast storage never will.
        assert_eq!(
            Ok(()),
            storage
                .write_blob(
                    instance.clone(),
                    content1.digest,
                    content1.bytes.clone(),
                    DriverState::default(),
                )
                .await
        );
    }
}
