// Copyright 2022 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::sync::Arc;

use async_trait::async_trait;
use bytes::{Bytes, BytesMut};

use crate::driver::{
    BlobStorage, BoxReadStream, DriverState, Instance, StorageError, StreamingWriteError,
    WriteAttemptOps,
};
use crate::Digest;

/// Represents how to read and write blobs by digest into "small" storage managed by the driver.
/// Unlike `BlobStorage`, this trait intentionally does not support streaming reads and writes.
/// This allows for drivers that optimize for or needing access to the entire blob at once.
#[async_trait]
pub trait SmallBlobStorage {
    /// Given a list of digests, return the digests that are **not** stored by this driver.
    ///
    /// This is used to implement the FindMissingBlobs RPC from the CAS API.
    async fn find_missing_blobs(
        &self,
        instance: Instance,
        digests: Vec<Digest>,
        state: DriverState,
    ) -> Result<Vec<Digest>, StorageError>;

    /// Return a `Bytes` with the bytes comprising the content of the `digest`.
    async fn read_blob(
        &self,
        instance: Instance,
        digest: Digest,
        state: DriverState,
    ) -> Result<Option<Bytes>, StorageError>;

    /// Store the blob provided in the given `Bytes`.
    async fn write_blob(
        &self,
        instance: Instance,
        digest: Digest,
        content: Bytes,
        state: DriverState,
    ) -> Result<(), StorageError>;
}

#[async_trait]
impl<T> SmallBlobStorage for Box<T>
where
    T: SmallBlobStorage + ?Sized + Send + Sync + 'static,
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
        state: DriverState,
    ) -> Result<Option<Bytes>, StorageError> {
        (**self).read_blob(instance, digest, state).await
    }

    async fn write_blob(
        &self,
        instance: Instance,
        digest: Digest,
        content: Bytes,
        state: DriverState,
    ) -> Result<(), StorageError> {
        (**self).write_blob(instance, digest, content, state).await
    }
}

/// Adapts a `SmallBlobStorage` into a `BlobStorage`
pub struct SmallBlobStorageAdapter<T> {
    inner: Arc<T>,
}

enum Content {
    Empty,
    First(Bytes),
    Merging(BytesMut),
}

struct WriteAttempt<T> {
    instance: Instance,
    digest: Digest,
    inner: Arc<T>,
    content: Content,
    state: DriverState,
}

impl<T> SmallBlobStorageAdapter<T> {
    pub fn new(inner: T) -> Self {
        Self {
            inner: Arc::new(inner),
        }
    }
}

#[async_trait]
impl<T> BlobStorage for SmallBlobStorageAdapter<T>
where
    T: SmallBlobStorage + Send + Sync + 'static,
{
    async fn find_missing_blobs(
        &self,
        instance: Instance,
        digests: Vec<Digest>,
        state: DriverState,
    ) -> Result<Vec<Digest>, StorageError> {
        self.inner
            .find_missing_blobs(instance, digests, state)
            .await
    }

    async fn read_blob(
        &self,
        instance: Instance,
        digest: Digest,
        _max_batch_size: usize,
        read_offset: Option<usize>,
        read_limit: Option<usize>,
        state: DriverState,
    ) -> Result<Option<BoxReadStream>, StorageError> {
        let content = match self.inner.read_blob(instance, digest, state).await {
            Ok(Some(c)) => c,
            Ok(None) => return Ok(None),
            Err(err) => return Err(err),
        };

        let start_index = read_offset.unwrap_or(0);
        if start_index > content.len() {
            return Err(StorageError::OutOfRange(
                "read_offset".to_string(),
                start_index,
            ));
        }

        let end_index = match read_limit {
            Some(0) | None => content.len(),
            Some(i) => (start_index + i).min(content.len()),
        };

        let content = if start_index > 0 || end_index != content.len() {
            content.slice(start_index..end_index)
        } else {
            content
        };

        let stream: BoxReadStream = Box::pin(futures::stream::iter(vec![Ok(content)]));
        Ok(Some(stream))
    }

    async fn begin_write_blob(
        &self,
        instance: Instance,
        digest: Digest,
        state: DriverState,
    ) -> Result<Box<dyn WriteAttemptOps + Send + Sync + 'static>, StreamingWriteError> {
        let attempt = WriteAttempt {
            instance,
            digest,
            inner: self.inner.clone(),
            content: Content::Empty,
            state,
        };
        Ok(Box::new(attempt) as Box<dyn WriteAttemptOps + Send + Sync + 'static>)
    }
}

#[async_trait]
impl<T> WriteAttemptOps for WriteAttempt<T>
where
    T: SmallBlobStorage + Send + Sync + 'static,
{
    async fn write(&mut self, chunk: Bytes) -> Result<(), StreamingWriteError> {
        // Update the data that will be stored by merging this chunk into the chunk that is
        // being built.
        //
        // Note: This driver is optimized for the case where a single call to `.write` is made
        // (whether because the REAPI client used the BatchUpdateBlobs CAS API which passes the
        // entire blob or wrote a single chunk via the ByteStream Write API). Thus, this function
        // stores the first chunk received (and concatenates any subsequent chunks received, but
        // "hopes" it does not have to do that).
        match &mut self.content {
            Content::Empty => {
                self.content = Content::First(chunk);
            }
            Content::First(first_chunk) => {
                let mut new_content =
                    BytesMut::with_capacity(self.digest.size_bytes.max(first_chunk.len()));
                new_content.extend_from_slice(&first_chunk[..]);
                if (new_content.capacity() - new_content.len()) < chunk.len() {
                    new_content.reserve(chunk.len());
                }
                new_content.extend_from_slice(&chunk[..]);
                self.content = Content::Merging(new_content);
            }
            Content::Merging(content) => {
                content.extend(chunk);
            }
        };

        Ok(())
    }

    async fn commit(mut self: Box<Self>) -> Result<(), StreamingWriteError> {
        let content = match self.content {
            Content::Empty => Bytes::new(),
            Content::First(c) => c,
            Content::Merging(c) => c.freeze(),
        };

        Ok(self
            .inner
            .write_blob(self.instance, self.digest, content, self.state)
            .await?)
    }
}

/// Adapts a `BlobStorage` into a `SmallBlobStorage`.
///
/// NB: This type is a convenience, but it will generally be more efficient to directly implement
/// `SmallBlobStorage` for a particular driver.
pub struct BlobStorageAdapter<T> {
    inner: Arc<T>,
}

impl<T> BlobStorageAdapter<T>
where
    T: BlobStorage + Send + Sync + 'static,
{
    const MAX_BATCH_TOTAL_SIZE_BYTES: usize = 1024 * 1024;

    pub fn new(inner: T) -> Self {
        Self {
            inner: Arc::new(inner),
        }
    }
}

#[async_trait]
impl<T> SmallBlobStorage for BlobStorageAdapter<T>
where
    T: BlobStorage + Send + Sync + 'static,
{
    async fn find_missing_blobs(
        &self,
        instance: Instance,
        digests: Vec<Digest>,
        state: DriverState,
    ) -> Result<Vec<Digest>, StorageError> {
        self.inner
            .find_missing_blobs(instance, digests, state)
            .await
    }

    async fn read_blob(
        &self,
        instance: Instance,
        digest: Digest,
        state: DriverState,
    ) -> Result<Option<Bytes>, StorageError> {
        let maybe_stream = self
            .inner
            .read_blob(
                instance,
                digest,
                Self::MAX_BATCH_TOTAL_SIZE_BYTES,
                None,
                None,
                state,
            )
            .await?;
        let stream = if let Some(s) = maybe_stream {
            s
        } else {
            return Ok(None);
        };

        Ok(Some(crate::bytes::consolidate_stream(stream).await?))
    }

    async fn write_blob(
        &self,
        instance: Instance,
        digest: Digest,
        content: Bytes,
        state: DriverState,
    ) -> Result<(), StorageError> {
        let write = async move {
            let mut attempt = self
                .inner
                .begin_write_blob(instance, digest, state.clone())
                .await?;
            attempt.write(content).await?;
            attempt.commit().await
        };
        write
            .await
            .or_else(StreamingWriteError::ok_if_already_exists)
    }
}

#[cfg(test)]
mod tests {
    use bytes::Bytes;

    use crate::bytes::consolidate_stream;
    use crate::driver::small::{BlobStorageAdapter, SmallBlobStorage, SmallBlobStorageAdapter};
    use crate::driver::{BlobStorage, DriverState, Instance, MemoryStorage};
    use crate::testutil::{SmallMemoryStorage, TestData};

    #[tokio::test]
    async fn small_adaptor_check_basic_read_and_write() {
        let instance = Instance::from("main");
        let content = TestData::from_static(b"foobarxyzzy");

        let storage = SmallMemoryStorage::new();
        let mut storage = SmallBlobStorageAdapter::new(storage);
        storage.ensure_instance(&instance, DriverState::default());

        let missing_blobs = storage
            .find_missing_blobs(
                instance.clone(),
                vec![content.digest],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert_eq!(missing_blobs, vec![content.digest]);

        let mut attempt = storage
            .begin_write_blob(instance.clone(), content.digest, DriverState::default())
            .await
            .unwrap();
        let chunk_size = content.bytes.len() / 3; // this is 3 so we test Content::Merging
        let mut i = 0;
        while i < content.bytes.len() {
            attempt
                .write(
                    content
                        .bytes
                        .slice(i..content.bytes.len().min(i + chunk_size)),
                )
                .await
                .unwrap();
            i += chunk_size;
        }
        attempt.commit().await.unwrap();

        let missing_blobs = storage
            .find_missing_blobs(
                instance.clone(),
                vec![content.digest],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert!(missing_blobs.is_empty());

        let stream = storage
            .read_blob(
                instance.clone(),
                content.digest,
                3,
                None,
                None,
                DriverState::default(),
            )
            .await
            .unwrap()
            .unwrap();
        let actual_content = consolidate_stream(stream).await.unwrap();
        assert_eq!(content.bytes, actual_content);

        // Test that a zero length read at the end of the blob is allowed.
        let stream = storage
            .read_blob(
                instance.clone(),
                content.digest,
                3,
                Some(content.bytes.len()),
                None,
                DriverState::default(),
            )
            .await
            .unwrap()
            .unwrap();
        let actual_content = consolidate_stream(stream).await.unwrap();
        assert_eq!(Bytes::from_static(&[]), actual_content);
    }

    #[tokio::test]
    async fn adaptor_check_basic_read_and_write() {
        let instance = Instance::from("main");
        let content = TestData::from_static(b"foobarxyzzy");

        let mut storage = MemoryStorage::new();
        // TODO: `ensure_instance` is unused except for in `MemoryStorage`: `BlobStorageAdapter`
        // will not call it.
        storage.ensure_instance(&instance, DriverState::default());
        let storage = BlobStorageAdapter::new(storage);

        let missing_blobs = storage
            .find_missing_blobs(
                instance.clone(),
                vec![content.digest],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert_eq!(missing_blobs, vec![content.digest]);

        storage
            .write_blob(
                instance.clone(),
                content.digest,
                content.bytes.clone(),
                DriverState::default(),
            )
            .await
            .unwrap();

        let missing_blobs = storage
            .find_missing_blobs(
                instance.clone(),
                vec![content.digest],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert!(missing_blobs.is_empty());

        let actual_content = storage
            .read_blob(instance.clone(), content.digest, DriverState::default())
            .await
            .unwrap()
            .unwrap();
        assert_eq!(content.bytes, actual_content);
    }
}
