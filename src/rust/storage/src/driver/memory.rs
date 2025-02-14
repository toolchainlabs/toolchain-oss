// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::collections::{HashMap, HashSet};
use std::sync::Arc;

use async_trait::async_trait;
use bytes::{Bytes, BytesMut};
use digest::Digest;
use parking_lot::Mutex;

use super::Instance;
use crate::driver::{
    BoxReadStream, DriverState, StorageError, StreamingWriteError, WriteAttemptOps,
};

pub struct MemoryWriteAttempt {
    instance: Instance,
    digest: Digest,
    content: BytesMut,
    storage: Arc<Mutex<Inner>>,
}

struct Inner {
    /// Stores the content associated with a digest.
    blobs: HashMap<Digest, Bytes>,

    /// Stores whether a particular blob is visible in particular instance.
    ///
    /// Note: This is intended to allow this driver to be used to implement the Action Cache
    /// which requires that ActionResult protos only be visible if they were written by an
    /// authorized caller. (This may require visiting.)
    blobs_by_instance: HashMap<Instance, HashSet<Digest>>,
}

#[derive(Clone)]
pub struct MemoryStorage {
    inner: Arc<Mutex<Inner>>,
}

#[async_trait]
impl super::WriteAttemptOps for MemoryWriteAttempt {
    async fn write(&mut self, batch: Bytes) -> Result<(), StreamingWriteError> {
        self.content.extend_from_slice(&batch[..]);
        Ok(())
    }

    async fn commit(self: Box<Self>) -> Result<(), StreamingWriteError> {
        let mut inner = self.storage.lock();
        let instance = self.instance.clone();

        inner.setup_instance(&instance);

        let digest = self.digest;
        inner
            .blobs_by_instance
            .entry(instance)
            .and_modify(move |blobs| {
                blobs.insert(digest);
            })
            .or_insert_with(move || {
                let mut blobs = HashSet::new();
                blobs.insert(digest);
                blobs
            });

        let content = self.content.freeze();
        inner.blobs.entry(digest).or_insert(content);

        Ok(())
    }
}

#[async_trait]
impl super::BlobStorage for MemoryStorage {
    async fn find_missing_blobs(
        &self,
        instance: Instance,
        digests: Vec<Digest>,
        _state: DriverState,
    ) -> Result<Vec<Digest>, StorageError> {
        let inner = self.inner.lock();

        let instance_blobs = inner.get_blobs_for_instance(&instance)?;

        let mut missing_digests = Vec::new();
        for digest in digests.into_iter() {
            if digest == Digest::EMPTY {
                continue;
            }
            if !instance_blobs.contains(&digest) || !inner.blobs.contains_key(&digest) {
                missing_digests.push(digest);
            }
        }

        Ok(missing_digests)
    }

    async fn read_blob(
        &self,
        instance: Instance,
        digest: Digest,
        max_batch_size: usize,
        read_offset: Option<usize>,
        read_limit: Option<usize>,
        _state: DriverState,
    ) -> Result<Option<BoxReadStream>, StorageError> {
        let inner = self.inner.lock();
        let instance_blobs = inner.get_blobs_for_instance(&instance)?;

        let blob = match (instance_blobs.contains(&digest), inner.blobs.get(&digest)) {
            (true, Some(b)) => b.clone(),
            _ => return Ok(None),
        };

        let stream = async_stream::stream! {
          let mut offset = read_offset.unwrap_or_default();
          let final_offset = offset + read_limit.unwrap_or(blob.len()).min(blob.len());

          while offset < final_offset {
            let start: usize = offset;
            let end: usize = (start + max_batch_size).min(blob.len());
            let chunk = blob.slice(start..end);
            yield Ok(chunk);
            offset = end;
          }
        };

        Ok(Some(Box::pin(stream)))
    }

    async fn begin_write_blob(
        &self,
        instance: Instance,
        digest: Digest,
        _state: DriverState,
    ) -> Result<Box<dyn WriteAttemptOps + Send + Sync + 'static>, StreamingWriteError> {
        if self
            .inner
            .lock()
            .get_blobs_for_instance(&instance)?
            .contains(&digest)
        {
            return Err(StreamingWriteError::AlreadyExists);
        }

        let content = BytesMut::with_capacity(digest.size_bytes);

        let attempt = MemoryWriteAttempt {
            instance,
            content,
            digest,
            storage: self.inner.clone(),
        };

        Ok(Box::new(attempt))
    }

    fn ensure_instance(&mut self, instance: &Instance, _state: DriverState) {
        let mut inner = self.inner.lock();
        inner.setup_instance(instance);
    }
}

impl MemoryStorage {
    pub fn new() -> Self {
        MemoryStorage {
            inner: Arc::new(Mutex::new(Inner {
                blobs: HashMap::new(),
                blobs_by_instance: HashMap::new(),
            })),
        }
    }
}

impl Inner {
    fn setup_instance(&mut self, instance: &Instance) {
        if !self.blobs_by_instance.contains_key(instance) {
            self.blobs_by_instance
                .insert(instance.clone(), HashSet::new());
        }
    }

    fn get_blobs_for_instance(
        &self,
        instance: &Instance,
    ) -> Result<&HashSet<Digest>, StorageError> {
        self.blobs_by_instance
            .get(instance)
            .ok_or_else(|| "unknown instance".to_owned().into())
    }
}

#[cfg(test)]
mod tests {
    use futures::StreamExt;

    use super::MemoryStorage;
    use crate::driver::{BlobStorage, DriverState, Instance};
    use crate::testutil::TestData;

    #[tokio::test]
    async fn test_basic_read_write() {
        let mut storage = MemoryStorage::new();
        let instance = Instance::from("main");
        storage.ensure_instance(&instance, DriverState::default());

        let content = TestData::from_static(b"foobar");

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

        let mut stream = storage
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
        let batch1 = stream.next().await.unwrap();
        assert_eq!(batch1, Ok(content.bytes.slice(0..3)));
        let batch2 = stream.next().await.unwrap();
        assert_eq!(batch2, Ok(content.bytes.slice(3..)));
        assert!(stream.next().await.is_none());
    }

    #[tokio::test]
    async fn dropped_write_attempt() {
        let mut storage = MemoryStorage::new();
        let instance = Instance::from("main");
        storage.ensure_instance(&instance, DriverState::default());

        let content = TestData::from_static(b"foobar");

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
        attempt
            .write(content.bytes.slice(0..content.bytes.len() / 2))
            .await
            .unwrap();
        attempt
            .write(content.bytes.slice(content.bytes.len() / 2..))
            .await
            .unwrap();

        drop(attempt);

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
}
