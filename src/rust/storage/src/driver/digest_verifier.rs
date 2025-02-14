// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::fmt::Debug;

use async_trait::async_trait;
use bytes::Bytes;
use digest::Digest;
use futures::StreamExt;
use sha2::{Digest as Sha256Digest, Sha256};

use crate::driver::{
    BlobStorage, BoxReadStream, DriverState, Instance, StorageError, StreamingWriteError,
    WriteAttemptOps,
};

/// A `BlobStorage` that wraps an underlying `BlobStorage` implementation and computes the
/// digest of content as it is written. This is used to enforce that the digest of content matches
/// the digest provided by the client on writes.
///
/// Use `ReadDigestVerifier` instead to verify digests as they are read (to detect corruption
/// in a storage backend).
#[derive(Debug)]
pub struct WriteDigestVerifier<BS> {
    underlying: BS,
}

impl<BS: Clone> Clone for WriteDigestVerifier<BS> {
    fn clone(&self) -> Self {
        WriteDigestVerifier {
            underlying: self.underlying.clone(),
        }
    }
}

pub struct WriteAttempt {
    underlying: Box<dyn WriteAttemptOps + Send + Sync + 'static>,
    hasher: Sha256,
    expected_digest: Digest,
    written: usize,
}

#[async_trait]
impl WriteAttemptOps for WriteAttempt {
    async fn write(&mut self, batch: Bytes) -> Result<(), StreamingWriteError> {
        self.written += batch.len();
        self.hasher.update(batch.as_ref());
        self.underlying.write(batch).await
    }

    async fn commit(self: Box<Self>) -> Result<(), StreamingWriteError> {
        let actual_size = self.written;
        let expected_size = self.expected_digest.size_bytes;
        if actual_size != expected_size {
            return Err(StorageError::InvalidSize {
                expected_size,
                is_data_loss: false,
            }
            .into());
        }

        let hash = self.hasher.finalize();
        let computed_digest = Digest::from_slice(&hash, expected_size)?;
        if computed_digest != self.expected_digest {
            return Err(StorageError::InvalidHash {
                expected_digest: self.expected_digest,
                actual_digest: computed_digest,
                is_data_loss: false,
            }
            .into());
        }

        self.underlying.commit().await
    }
}

#[async_trait]
impl<BS> BlobStorage for WriteDigestVerifier<BS>
where
    BS: BlobStorage + Send + Sync + 'static,
{
    async fn find_missing_blobs(
        &self,
        instance: Instance,
        digests: Vec<Digest>,
        state: DriverState,
    ) -> Result<Vec<Digest>, StorageError> {
        self.underlying
            .find_missing_blobs(instance, digests, state)
            .await
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
        self.underlying
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
        let attempt = self
            .underlying
            .begin_write_blob(instance, digest, state)
            .await?;
        let wrapped_attempt = WriteAttempt {
            underlying: attempt,
            hasher: Sha256::default(),
            expected_digest: digest,
            written: 0,
        };
        Ok(Box::new(wrapped_attempt))
    }

    fn ensure_instance(&mut self, instance: &Instance, state: DriverState) {
        self.underlying.ensure_instance(instance, state)
    }
}

impl<BS> WriteDigestVerifier<BS> {
    pub fn new(underlying: BS) -> Self {
        WriteDigestVerifier { underlying }
    }
}

/// A `BlobStorage` that wraps an underlying `BlobStorage` implementation and computes the
/// digest of content as it is read. This is used to enforce that the digest of content matches
/// the original digest of that data when it is read again, which can help detect storage
/// corruption.
///
/// Use `WriteDigestVerifier` instead to verify digests as they are written.
#[derive(Debug)]
pub struct ReadDigestVerifier<BS> {
    underlying: BS,
}

#[async_trait]
impl<BS> BlobStorage for ReadDigestVerifier<BS>
where
    BS: BlobStorage + Send + Sync + 'static,
{
    async fn find_missing_blobs(
        &self,
        instance: Instance,
        digests: Vec<Digest>,
        state: DriverState,
    ) -> Result<Vec<Digest>, StorageError> {
        self.underlying
            .find_missing_blobs(instance, digests, state)
            .await
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
        let stream_opt = self
            .underlying
            .read_blob(
                instance,
                digest,
                max_batch_size,
                read_offset,
                read_limit,
                state,
            )
            .await?;

        let mut stream = match stream_opt {
            Some(stream) => stream,
            None => return Ok(None),
        };

        // Note: This does not use the `async_stream::try_stream!` macro because that would
        // make emitting the `Err` values later in the logic look weird by relying on the `?`
        // operator to emit them as a side effect.
        let stream: BoxReadStream = Box::pin(async_stream::stream! {
            let mut hasher = Sha256::default();
            let mut actual_size = 0;

            while let Some(chunk_result) = stream.next().await {
                let chunk = match chunk_result {
                    Ok(chunk) => chunk,
                    Err(err) => {
                        yield Err(err);
                        return;
                    }
                };
                actual_size += chunk.len();
                hasher.update(chunk.as_ref());
                yield Ok(chunk);
            }

            if actual_size != digest.size_bytes {
                yield Err(StorageError::InvalidSize {
                    expected_size: digest.size_bytes,
                    is_data_loss: true,
                });
                return;
            }

            let hash = hasher.finalize();
            let actual_digest = Digest::from_slice(&hash, digest.size_bytes)?;
            if actual_digest != digest {
                yield Err(StorageError::InvalidHash {
                    expected_digest: digest,
                    actual_digest,
                    is_data_loss: true,
                });
            }
        });

        Ok(Some(stream))
    }

    async fn begin_write_blob(
        &self,
        instance: Instance,
        digest: Digest,
        state: DriverState,
    ) -> Result<Box<dyn WriteAttemptOps + Send + Sync + 'static>, StreamingWriteError> {
        self.underlying
            .begin_write_blob(instance, digest, state)
            .await
    }

    fn ensure_instance(&mut self, instance: &Instance, state: DriverState) {
        self.underlying.ensure_instance(instance, state);
    }
}

impl<BS> ReadDigestVerifier<BS> {
    pub fn new(underlying: BS) -> Self {
        ReadDigestVerifier { underlying }
    }
}

#[cfg(test)]
mod tests {
    use async_trait::async_trait;
    use bytes::Bytes;
    use digest::Digest;

    use super::{ReadDigestVerifier, WriteDigestVerifier};
    use crate::bytes::consolidate_stream;
    use crate::driver::{
        BlobStorage, BoxReadStream, DriverState, Instance, MemoryStorage, StorageError,
        StreamingWriteError, WriteAttemptOps,
    };
    use crate::testutil::TestData;

    #[tokio::test]
    async fn write_good_data() {
        let mut storage = WriteDigestVerifier::new(MemoryStorage::new());
        let instance = Instance::from("main");
        storage.ensure_instance(&instance, DriverState::default());

        let content = TestData::from_static(b"foobar");

        let mut attempt = storage
            .begin_write_blob(instance.clone(), content.digest, DriverState::default())
            .await
            .unwrap();
        attempt
            .write(content.bytes.slice(0..content.bytes.len() / 2))
            .await
            .unwrap();
        attempt
            .write(content.bytes.slice(content.bytes.len() / 2..))
            .await
            .unwrap();
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
    }

    #[tokio::test]
    async fn write_bad_data() {
        let mut storage = WriteDigestVerifier::new(MemoryStorage::new());
        let instance = Instance::from("main");
        storage.ensure_instance(&instance, DriverState::default());

        let content = TestData::from_static(b"foobar");

        let mut attempt = storage
            .begin_write_blob(instance.clone(), content.digest, DriverState::default())
            .await
            .unwrap();
        // Note: We are writing the second half first, which should make the digest invalid.
        attempt
            .write(content.bytes.slice(content.bytes.len() / 2..))
            .await
            .unwrap();
        attempt
            .write(content.bytes.slice(0..content.bytes.len() / 2))
            .await
            .unwrap();
        let err = attempt.commit().await.unwrap_err().unwrap_storage_error();
        assert!(matches!(err, StorageError::InvalidHash { .. }));

        let missing_blobs = storage
            .find_missing_blobs(
                instance.clone(),
                vec![content.digest],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert_eq!(missing_blobs, vec![content.digest]);
    }

    #[tokio::test]
    async fn write_bad_size_small() {
        let mut storage = WriteDigestVerifier::new(MemoryStorage::new());
        let instance = Instance::from("main");
        storage.ensure_instance(&instance, DriverState::default());

        let content = TestData::from_static(b"foobar");

        let mut attempt = storage
            .begin_write_blob(instance.clone(), content.digest, DriverState::default())
            .await
            .unwrap();
        // Note: We are writing only the first half, which should fail validation
        attempt
            .write(content.bytes.slice(0..content.bytes.len() / 2))
            .await
            .unwrap();
        let err = attempt.commit().await.unwrap_err().unwrap_storage_error();
        assert!(matches!(err, StorageError::InvalidSize { .. }));

        let missing_blobs = storage
            .find_missing_blobs(
                instance.clone(),
                vec![content.digest],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert_eq!(missing_blobs, vec![content.digest]);
    }

    #[tokio::test]
    async fn bad_size_large() {
        let mut storage = WriteDigestVerifier::new(MemoryStorage::new());
        let instance = Instance::from("main");
        storage.ensure_instance(&instance, DriverState::default());

        let content = TestData::from_static(b"foobar");

        let mut attempt = storage
            .begin_write_blob(instance.clone(), content.digest, DriverState::default())
            .await
            .unwrap();
        // Note: We are writing the first half three times, which should fail validation
        let half_of_content_bytes = content.bytes.slice(0..content.bytes.len() / 2);
        attempt.write(half_of_content_bytes.clone()).await.unwrap();
        attempt.write(half_of_content_bytes.clone()).await.unwrap();
        attempt.write(half_of_content_bytes).await.unwrap();
        let err = attempt.commit().await.unwrap_err().unwrap_storage_error();
        assert!(matches!(err, StorageError::InvalidSize { .. }));

        let missing_blobs = storage
            .find_missing_blobs(
                instance.clone(),
                vec![content.digest],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert_eq!(missing_blobs, vec![content.digest]);
    }

    #[tokio::test]
    async fn read_good_data() {
        let content = TestData::from_static(b"foobar");

        let mut memory_storage = MemoryStorage::new();
        let instance = Instance::from("main");
        memory_storage.ensure_instance(&instance, DriverState::default());

        let mut attempt = memory_storage
            .begin_write_blob(instance.clone(), content.digest, DriverState::default())
            .await
            .unwrap();
        attempt.write(content.bytes.clone()).await.unwrap();
        attempt.commit().await.unwrap();

        let storage = ReadDigestVerifier::new(memory_storage);

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
        let data = consolidate_stream(stream).await.unwrap();
        assert_eq!(data, content.bytes);
    }

    struct ReadConstantBlobStorage {
        constant_content: Bytes,
    }

    #[async_trait]
    impl BlobStorage for ReadConstantBlobStorage {
        async fn find_missing_blobs(
            &self,
            _instance: Instance,
            _digests: Vec<Digest>,
            _state: DriverState,
        ) -> Result<Vec<Digest>, StorageError> {
            Err(StorageError::Internal("unimplemented".to_string()))
        }

        async fn read_blob(
            &self,
            _instance: Instance,
            _digest: Digest,
            _max_batch_size: usize,
            _read_offset: Option<usize>,
            _read_limit: Option<usize>,
            _state: DriverState,
        ) -> Result<Option<BoxReadStream>, StorageError> {
            let stream = Box::pin(futures::stream::iter(
                vec![Ok(self.constant_content.clone())].into_iter(),
            )) as BoxReadStream;
            Ok(Some(stream))
        }

        async fn begin_write_blob(
            &self,
            _instance: Instance,
            _digest: Digest,
            _state: DriverState,
        ) -> Result<Box<dyn WriteAttemptOps + Send + Sync + 'static>, StreamingWriteError> {
            Err(StorageError::Internal("unimplemented".to_string()).into())
        }
    }

    #[tokio::test]
    async fn read_bad_data_hash() {
        let good_content = TestData::from_static(b"foobar");
        let bad_content = TestData::from_static(b"barfoo");

        let instance = Instance::from("main");

        let storage = ReadConstantBlobStorage {
            constant_content: bad_content.bytes.clone(),
        };
        let storage = ReadDigestVerifier::new(storage);

        let stream = storage
            .read_blob(
                instance.clone(),
                good_content.digest,
                3,
                None,
                None,
                DriverState::default(),
            )
            .await
            .unwrap()
            .unwrap();
        let err = consolidate_stream(stream).await.unwrap_err();
        assert!(matches!(err, StorageError::InvalidHash { .. }));
    }

    #[tokio::test]
    async fn read_bad_data_size() {
        let good_content = TestData::from_static(b"foobar");
        let bad_content = TestData::from_static(b"helloworld");

        let instance = Instance::from("main");

        let storage = ReadConstantBlobStorage {
            constant_content: bad_content.bytes.clone(),
        };
        let storage = ReadDigestVerifier::new(storage);

        let stream = storage
            .read_blob(
                instance.clone(),
                good_content.digest,
                3,
                None,
                None,
                DriverState::default(),
            )
            .await
            .unwrap()
            .unwrap();
        let err = consolidate_stream(stream).await.unwrap_err();
        assert_eq!(
            err,
            StorageError::InvalidSize {
                expected_size: good_content.digest.size_bytes,
                is_data_loss: true,
            }
        );
    }
}
