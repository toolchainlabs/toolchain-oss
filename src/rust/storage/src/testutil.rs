// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::collections::HashMap;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;

use async_trait::async_trait;
use bytes::Bytes;
use parking_lot::Mutex;
use tokio::sync::Semaphore;

use crate::driver::{
    BlobStorage, BoxReadStream, DriverState, Instance, SmallBlobStorage, StorageError,
    StreamingWriteError, WriteAttemptOps,
};
use crate::Digest;

/// Container for digest/bytes of test content.
#[derive(Clone, Debug)]
pub struct TestData {
    /// The actual bytes of the content.
    pub bytes: Bytes,

    /// Digest of the content.
    pub digest: Digest,
}

impl TestData {
    pub fn from_static(content: &'static [u8]) -> Self {
        let bytes = Bytes::from_static(content);
        let digest = Digest::of_bytes(&bytes).expect("compute digest");
        Self { bytes, digest }
    }
}

#[derive(Clone, Debug)]
pub struct CountMethodCallsStorage<S> {
    inner: S,
    pub find_missing_blobs_count: Arc<AtomicUsize>,
    pub read_count: Arc<AtomicUsize>,
    pub write_count: Arc<AtomicUsize>,
}

#[async_trait]
impl<S> BlobStorage for CountMethodCallsStorage<S>
where
    S: BlobStorage + Send + Sync + 'static,
{
    async fn find_missing_blobs(
        &self,
        instance: Instance,
        digests: Vec<Digest>,
        state: DriverState,
    ) -> Result<Vec<Digest>, StorageError> {
        self.find_missing_blobs_count.fetch_add(1, Ordering::SeqCst);
        self.inner
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
        self.read_count.fetch_add(1, Ordering::SeqCst);
        self.inner
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
    ) -> Result<Box<dyn WriteAttemptOps + Send + Sync>, StreamingWriteError> {
        self.write_count.fetch_add(1, Ordering::SeqCst);
        self.inner.begin_write_blob(instance, digest, state).await
    }

    fn ensure_instance(&mut self, instance: &Instance, state: DriverState) {
        self.inner.ensure_instance(instance, state);
    }
}

#[async_trait]
impl<S> SmallBlobStorage for CountMethodCallsStorage<S>
where
    S: SmallBlobStorage + Send + Sync + 'static,
{
    async fn find_missing_blobs(
        &self,
        instance: Instance,
        digests: Vec<Digest>,
        state: DriverState,
    ) -> Result<Vec<Digest>, StorageError> {
        self.find_missing_blobs_count.fetch_add(1, Ordering::SeqCst);
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
        self.read_count.fetch_add(1, Ordering::SeqCst);
        self.inner.read_blob(instance, digest, state).await
    }

    async fn write_blob(
        &self,
        instance: Instance,
        digest: Digest,
        content: Bytes,
        state: DriverState,
    ) -> Result<(), StorageError> {
        self.write_count.fetch_add(1, Ordering::SeqCst);
        self.inner
            .write_blob(instance, digest, content, state)
            .await
    }
}

impl<S> CountMethodCallsStorage<S> {
    pub fn new(inner: S) -> Self {
        Self {
            inner,
            find_missing_blobs_count: Arc::new(AtomicUsize::new(0)),
            read_count: Arc::new(AtomicUsize::new(0)),
            write_count: Arc::new(AtomicUsize::new(0)),
        }
    }

    pub fn into_inner(self) -> S {
        self.inner
    }

    pub fn counts(&self) -> (usize, usize, usize) {
        (
            self.find_missing_blobs_count.load(Ordering::SeqCst),
            self.read_count.load(Ordering::SeqCst),
            self.write_count.load(Ordering::SeqCst),
        )
    }
}

pub struct AlwaysExistsStorage;

#[async_trait]
impl BlobStorage for AlwaysExistsStorage {
    async fn find_missing_blobs(
        &self,
        _: Instance,
        _: Vec<Digest>,
        _: DriverState,
    ) -> Result<Vec<Digest>, StorageError> {
        Ok(vec![])
    }

    async fn read_blob(
        &self,
        _: Instance,
        _: Digest,
        _: usize,
        _: Option<usize>,
        _: Option<usize>,
        _: DriverState,
    ) -> Result<Option<BoxReadStream>, StorageError> {
        Err(StorageError::Unavailable(
            "This storage claims that all values exist, but doesn't actually contain anything."
                .to_string(),
        ))
    }

    async fn begin_write_blob(
        &self,
        _: Instance,
        _: Digest,
        _: DriverState,
    ) -> Result<Box<dyn WriteAttemptOps + Send + Sync + 'static>, StreamingWriteError> {
        Err(StreamingWriteError::AlreadyExists)
    }

    fn ensure_instance(&mut self, _: &Instance, _: DriverState) {}
}

#[derive(Clone)]
pub struct SmallMemoryStorage {
    contents: Arc<Mutex<HashMap<Digest, Bytes>>>,
}

impl SmallMemoryStorage {
    pub fn new() -> Self {
        Self {
            contents: Arc::new(Mutex::new(HashMap::new())),
        }
    }
}

#[async_trait]
impl SmallBlobStorage for SmallMemoryStorage {
    async fn find_missing_blobs(
        &self,
        _instance: Instance,
        digests: Vec<Digest>,
        _state: DriverState,
    ) -> Result<Vec<Digest>, StorageError> {
        let contents = self.contents.lock();
        let missing_digests = digests
            .into_iter()
            .filter(|d| !contents.contains_key(d))
            .collect::<Vec<_>>();
        Ok(missing_digests)
    }

    async fn read_blob(
        &self,
        _instance: Instance,
        digest: Digest,
        _state: DriverState,
    ) -> Result<Option<Bytes>, StorageError> {
        let contents = self.contents.lock();
        let blob_opt = contents.get(&digest).cloned();
        Ok(blob_opt)
    }

    async fn write_blob(
        &self,
        _instance: Instance,
        digest: Digest,
        content: Bytes,
        _state: DriverState,
    ) -> Result<(), StorageError> {
        let mut contents = self.contents.lock();
        contents.insert(digest, content);
        Ok(())
    }
}

#[derive(Copy, Clone, Debug)]
pub enum WriteSemaphoreOperation {
    Increment,
    Acquire,
}

impl WriteSemaphoreOperation {
    async fn execute(&self, semaphore: Arc<Semaphore>) -> Result<(), String> {
        match self {
            WriteSemaphoreOperation::Increment => semaphore.add_permits(1),
            WriteSemaphoreOperation::Acquire => {
                let _ = semaphore.acquire().await.map_err(|e| e.to_string())?;
            }
        }
        Ok(())
    }
}

/// Either increments or acquires the provided semaphore on writes.
///
/// The increment mode allows tests to detect when a write actually occurred to avoid flaky
/// sleeps to try and hope the write occurs. The acquire mode allows a test to block a write
/// from completing.
#[derive(Clone, Debug)]
pub struct WriteSemaphoreStorage<S> {
    inner: S,
    semaphore: Arc<Semaphore>,
    operation: WriteSemaphoreOperation,
}

#[async_trait]
impl<S> BlobStorage for WriteSemaphoreStorage<S>
where
    S: BlobStorage + Send + Sync + 'static,
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
        max_batch_size: usize,
        read_offset: Option<usize>,
        read_limit: Option<usize>,
        state: DriverState,
    ) -> Result<Option<BoxReadStream>, StorageError> {
        self.inner
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
        let attempt = self.inner.begin_write_blob(instance, digest, state).await?;
        Ok(Box::new(WriteSemaphoreWriteAttempt {
            semaphore: self.semaphore.clone(),
            attempt,
            operation: self.operation,
        }))
    }

    fn ensure_instance(&mut self, instance: &Instance, state: DriverState) {
        self.inner.ensure_instance(instance, state);
    }
}

struct WriteSemaphoreWriteAttempt {
    semaphore: Arc<Semaphore>,
    attempt: Box<dyn WriteAttemptOps + Send + Sync + 'static>,
    operation: WriteSemaphoreOperation,
}

#[async_trait]
impl WriteAttemptOps for WriteSemaphoreWriteAttempt {
    async fn write(&mut self, batch: Bytes) -> Result<(), StreamingWriteError> {
        self.attempt.write(batch).await
    }

    async fn commit(self: Box<Self>) -> Result<(), StreamingWriteError> {
        self.attempt.commit().await?;
        self.operation.execute(self.semaphore.clone()).await?;
        Ok(())
    }
}

#[async_trait]
impl<S> SmallBlobStorage for WriteSemaphoreStorage<S>
where
    S: SmallBlobStorage + Send + Sync + 'static,
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
        self.inner.read_blob(instance, digest, state).await
    }

    async fn write_blob(
        &self,
        instance: Instance,
        digest: Digest,
        content: Bytes,
        state: DriverState,
    ) -> Result<(), StorageError> {
        self.inner
            .write_blob(instance, digest, content, state)
            .await?;
        self.operation.execute(self.semaphore.clone()).await?;
        Ok(())
    }
}

impl<S> WriteSemaphoreStorage<S> {
    pub fn new(inner: S, semaphore: Arc<tokio::sync::Semaphore>) -> Self {
        Self::with_operation(inner, semaphore, WriteSemaphoreOperation::Increment)
    }

    pub fn with_operation(
        inner: S,
        semaphore: Arc<tokio::sync::Semaphore>,
        operation: WriteSemaphoreOperation,
    ) -> Self {
        Self {
            inner,
            semaphore,
            operation,
        }
    }

    pub fn into_inner(self) -> S {
        self.inner
    }

    pub fn get_ref(&self) -> &S {
        &self.inner
    }
}
