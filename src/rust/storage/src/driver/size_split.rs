// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use async_trait::async_trait;
use futures::future;

use crate::driver::{
    BlobStorage, BoxReadStream, DriverState, Instance, StorageError, StreamingWriteError,
    WriteAttemptOps,
};
use crate::Digest;

/// A `BlobStorage` that sends blobs smaller than the `split_size` to one `BlobStorage`
/// implementation and blobs equal to or larger than the `split_size` to another
/// `BlobStorage` implementation.
///
/// This is useful for putting smaller (and/or larger blobs) into storage backends that are
/// more efficient for those blobs given their sizes.
pub struct SizeSplitStorage<LT, GE> {
    split_size: usize,
    storage1: LT,
    storage2: GE,
}

#[async_trait]
impl<LT, GE> BlobStorage for SizeSplitStorage<LT, GE>
where
    LT: BlobStorage + Send + Sync + 'static,
    GE: BlobStorage + Send + Sync + 'static,
{
    async fn find_missing_blobs(
        &self,
        instance: Instance,
        digests: Vec<Digest>,
        state: DriverState,
    ) -> Result<Vec<Digest>, StorageError> {
        let (digests1, digests2) = digests
            .into_iter()
            .partition(|d| d.size_bytes < self.split_size);
        let (missing_digests1, missing_digest2) = future::try_join(
            self.storage1
                .find_missing_blobs(instance.clone(), digests1, state.clone()),
            self.storage2.find_missing_blobs(instance, digests2, state),
        )
        .await?;
        let missing_digests = missing_digests1
            .into_iter()
            .chain(missing_digest2)
            .collect();
        Ok(missing_digests)
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
        if digest.size_bytes < self.split_size {
            self.storage1
                .read_blob(
                    instance,
                    digest,
                    max_batch_size,
                    read_offset,
                    read_limit,
                    state,
                )
                .await
        } else {
            self.storage2
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
    }

    async fn begin_write_blob(
        &self,
        instance: Instance,
        digest: Digest,
        state: DriverState,
    ) -> Result<Box<dyn WriteAttemptOps + Send + Sync>, StreamingWriteError> {
        if digest.size_bytes < self.split_size {
            self.storage1
                .begin_write_blob(instance, digest, state)
                .await
        } else {
            self.storage2
                .begin_write_blob(instance, digest, state)
                .await
        }
    }

    fn ensure_instance(&mut self, instance: &Instance, state: DriverState) {
        self.storage1.ensure_instance(instance, state.clone());
        self.storage2.ensure_instance(instance, state);
    }
}

impl<LT, GE> SizeSplitStorage<LT, GE>
where
    LT: BlobStorage + Send + Sync + 'static,
    GE: BlobStorage + Send + Sync + 'static,
{
    /// Create a new `SizeSwitchStorage` with the specified `split_size` and child
    /// storage implementations.
    pub fn new(split_size: usize, storage1: LT, storage2: GE) -> Self {
        SizeSplitStorage {
            split_size,
            storage1,
            storage2,
        }
    }

    /// Consume this `BlobStorage` and return the child storage implementations.
    pub fn into_inner(self) -> (LT, GE) {
        (self.storage1, self.storage2)
    }
}

#[cfg(test)]
mod tests {
    use crate::bytes::consolidate_stream;
    use crate::driver::{BlobStorage, DriverState, Instance, MemoryStorage, SizeSplitStorage};
    use crate::testutil::TestData;

    #[tokio::test]
    async fn size_split_storage() {
        let content1 = TestData::from_static(b"foobar");
        let content2 = TestData::from_static(b"foobarxyzzy");

        let child_storage1 = MemoryStorage::new();
        let child_storage2 = MemoryStorage::new();
        let mut storage =
            SizeSplitStorage::new(1 + content1.bytes.len(), child_storage1, child_storage2);

        let instance = Instance::from("main");
        storage.ensure_instance(&instance, DriverState::default());

        // Load both blobs into the storage. They should be split between the two child
        // storage implementations.

        let mut attempt = storage
            .begin_write_blob(instance.clone(), content1.digest, DriverState::default())
            .await
            .unwrap();
        attempt.write(content1.bytes.clone()).await.unwrap();
        attempt.commit().await.unwrap();

        let mut attempt = storage
            .begin_write_blob(instance.clone(), content2.digest, DriverState::default())
            .await
            .unwrap();
        attempt.write(content2.bytes.clone()).await.unwrap();
        attempt.commit().await.unwrap();

        // Existence checks for both blobs should pass.
        let missing_blobs = storage
            .find_missing_blobs(
                instance.clone(),
                vec![content1.digest, content2.digest],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert!(missing_blobs.is_empty());

        // Read back both blobs using the size split storage.
        let stream = storage
            .read_blob(
                instance.clone(),
                content1.digest,
                1024,
                None,
                None,
                DriverState::default(),
            )
            .await
            .unwrap()
            .unwrap();
        let actual_content1 = consolidate_stream(stream).await.unwrap();
        assert_eq!(content1.bytes, actual_content1);

        let stream = storage
            .read_blob(
                instance.clone(),
                content2.digest,
                1024,
                None,
                None,
                DriverState::default(),
            )
            .await
            .unwrap()
            .unwrap();
        let actual_content2 = consolidate_stream(stream).await.unwrap();
        assert_eq!(content2.bytes, actual_content2);

        // Finally, recover the child storage implementations and confirm that each only contains
        // the expected blobs.
        let (storage1, storage2) = storage.into_inner();
        let missing_blobs = storage1
            .find_missing_blobs(
                instance.clone(),
                vec![content1.digest, content2.digest],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert_eq!(missing_blobs, vec![content2.digest]);
        let missing_blobs = storage2
            .find_missing_blobs(
                instance.clone(),
                vec![content1.digest, content2.digest],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert_eq!(missing_blobs, vec![content1.digest]);
    }
}
