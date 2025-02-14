// Copyright 2022 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::collections::HashSet;

use async_trait::async_trait;
use bytes::Bytes;
use tokio::sync::mpsc;
use tokio::task::JoinHandle;

use crate::driver::{
    BlobStorage, BoxReadStream, DriverState, Instance, StorageError, StreamingWriteError,
    WriteAttemptOps,
};
use crate::Digest;

/// A `BlobStorage` that allows "dark launching" a new feature by redirecting traffic for
/// some customers to a new backend.
pub struct DarkLaunchStorage<S1, S2> {
    storage1: S1,
    storage2: S2,
    storage2_instance_names: HashSet<String>,
    write_to_secondary: bool,
    purpose: &'static str,
}

enum StorageChoice {
    Storage1,
    Storage2,
}

#[derive(Debug)]
enum SecondaryWriteChannelOp {
    Write(Bytes),
    Commit,
}

struct WriteAttempt {
    primary_attempt: Box<dyn WriteAttemptOps + Send + Sync>,
    secondary_sender: mpsc::UnboundedSender<SecondaryWriteChannelOp>,
    _secondary_processor_fut: JoinHandle<()>,
}

#[async_trait]
impl WriteAttemptOps for WriteAttempt {
    async fn write(&mut self, batch: Bytes) -> Result<(), StreamingWriteError> {
        self.secondary_sender
            .send(SecondaryWriteChannelOp::Write(batch.clone()))
            .unwrap();
        self.primary_attempt.write(batch).await
    }

    async fn commit(self: Box<Self>) -> Result<(), StreamingWriteError> {
        self.secondary_sender
            .send(SecondaryWriteChannelOp::Commit)
            .unwrap();
        self.primary_attempt.commit().await
    }
}

impl WriteAttempt {
    pub fn new(
        primary_attempt: Box<dyn WriteAttemptOps + Send + Sync>,
        second_attempt_opt: Option<Box<dyn WriteAttemptOps + Send + Sync>>,
        purpose: &'static str,
    ) -> Self {
        let (sender, mut receiver) = mpsc::unbounded_channel::<SecondaryWriteChannelOp>();

        let secondary_processor_fut = if let Some(mut secondary_attempt) = second_attempt_opt {
            tokio::spawn(async move {
                let mut saw_error = false;
                let mut do_commit = false;

                while let Some(op) = receiver.recv().await {
                    match op {
                        SecondaryWriteChannelOp::Write(batch) => {
                            if saw_error {
                                continue;
                            }

                            let result = secondary_attempt.write(batch).await;
                            if result.is_err() {
                                metrics::counter!(
                                    "toolchain_storage_secondary_write_errors_total",
                                    1,
                                    "driver" => "dark_launch",
                                    "purpose" => purpose,
                                );
                                saw_error = true;
                            }
                        }
                        SecondaryWriteChannelOp::Commit => {
                            do_commit = true;
                            break;
                        }
                    }
                }

                if do_commit && !saw_error {
                    let result = secondary_attempt.commit().await;
                    if result.is_err() {
                        metrics::counter!(
                            "toolchain_storage_secondary_write_errors_total",
                            1,
                            "driver" => "dark_launch",
                            "purpose" => purpose,
                        );
                    }
                }
            })
        } else {
            tokio::spawn(async move { while receiver.recv().await.is_some() {} })
        };

        WriteAttempt {
            primary_attempt,
            secondary_sender: sender,
            _secondary_processor_fut: secondary_processor_fut,
        }
    }
}

#[async_trait]
impl<S1, S2> BlobStorage for DarkLaunchStorage<S1, S2>
where
    S1: BlobStorage + Send + Sync + 'static,
    S2: BlobStorage + Send + Sync + 'static,
{
    async fn find_missing_blobs(
        &self,
        instance: Instance,
        digests: Vec<Digest>,
        state: DriverState,
    ) -> Result<Vec<Digest>, StorageError> {
        match self.choose_storage(&instance) {
            StorageChoice::Storage1 => {
                self.storage1
                    .find_missing_blobs(instance, digests, state)
                    .await
            }
            StorageChoice::Storage2 => {
                self.storage2
                    .find_missing_blobs(instance, digests, state)
                    .await
            }
        }
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
        match self.choose_storage(&instance) {
            StorageChoice::Storage1 => {
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
            }
            StorageChoice::Storage2 => {
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
    }

    async fn begin_write_blob(
        &self,
        instance: Instance,
        digest: Digest,
        state: DriverState,
    ) -> Result<Box<dyn WriteAttemptOps + Send + Sync + 'static>, StreamingWriteError> {
        let (primary_attempt, secondary_attempt_opt) = match self.choose_storage(&instance) {
            StorageChoice::Storage1 => {
                let attempt1 = self
                    .storage1
                    .begin_write_blob(instance.clone(), digest, state.clone())
                    .await?;

                let attempt2_opt = if self.write_to_secondary {
                    Some(
                        self.storage2
                            .begin_write_blob(instance, digest, state)
                            .await?,
                    )
                } else {
                    None
                };

                (attempt1, attempt2_opt)
            }
            StorageChoice::Storage2 => {
                let attempt2 = self
                    .storage2
                    .begin_write_blob(instance.clone(), digest, state.clone())
                    .await?;

                let attempt1_opt = if self.write_to_secondary {
                    Some(
                        self.storage1
                            .begin_write_blob(instance, digest, state)
                            .await?,
                    )
                } else {
                    None
                };

                (attempt2, attempt1_opt)
            }
        };

        let merged_attempt =
            WriteAttempt::new(primary_attempt, secondary_attempt_opt, self.purpose);
        Ok(Box::new(merged_attempt))
    }

    fn ensure_instance(&mut self, instance: &Instance, state: DriverState) {
        self.storage1.ensure_instance(instance, state.clone());
        self.storage2.ensure_instance(instance, state);
    }
}

impl<S1, S2> DarkLaunchStorage<S1, S2>
where
    S1: BlobStorage + Send + Sync + 'static,
    S2: BlobStorage + Send + Sync + 'static,
{
    fn choose_storage(&self, instance: &Instance) -> StorageChoice {
        if self.storage2_instance_names.contains(&instance.name) {
            metrics::counter!(
                "toolchain_storage_dark_launch_choice", 1,
                "choice" => "2",
                "driver" => "dark_launch",
                "purpose" => self.purpose,
            );
            StorageChoice::Storage2
        } else {
            metrics::counter!(
                "toolchain_storage_dark_launch_choice", 1,
                "choice" => "1",
                "driver" => "dark_launch",
                "purpose" => self.purpose,
            );
            StorageChoice::Storage1
        }
    }

    pub fn new(
        storage1: S1,
        storage2: S2,
        storage2_instance_names: impl IntoIterator<Item = String>,
        write_to_secondary: bool,
        purpose: &'static str,
    ) -> Self {
        DarkLaunchStorage {
            storage1,
            storage2,
            storage2_instance_names: storage2_instance_names.into_iter().collect::<HashSet<_>>(),
            write_to_secondary,
            purpose,
        }
    }

    #[cfg(test)]
    pub fn into_inner(self) -> (S1, S2) {
        (self.storage1, self.storage2)
    }
}

#[cfg(test)]
mod tests {
    use std::sync::atomic::Ordering;
    use std::sync::Arc;
    use std::time::Duration;

    use tokio::sync::Semaphore;

    use super::DarkLaunchStorage;
    use crate::bytes::consolidate_stream;
    use crate::driver::{BlobStorage, DriverState, Instance, MemoryStorage};
    use crate::testutil::{CountMethodCallsStorage, TestData, WriteSemaphoreStorage};
    use crate::Digest;

    async fn acquire_and_forget(semaphore: &Semaphore, n: u32, timeout: Duration) {
        let permits = tokio::time::timeout(timeout, semaphore.acquire_many(n))
            .await
            .unwrap()
            .unwrap();
        permits.forget();
        assert_eq!(semaphore.available_permits(), 0);
    }

    async fn assert_missing_blobs<S>(
        storage: &S,
        instance: &Instance,
        digests_to_check: Vec<Digest>,
        expected_missing_digests: Vec<Digest>,
    ) where
        S: BlobStorage + Send + Sync + 'static,
    {
        let actual_missing_blobs = storage
            .find_missing_blobs(instance.clone(), digests_to_check, DriverState::default())
            .await
            .unwrap();
        assert_eq!(expected_missing_digests, actual_missing_blobs,);
    }

    #[tokio::test]
    async fn dark_launch_storage_writes_both_backends() {
        let content1 = TestData::from_static(b"foobar");
        let content2 = TestData::from_static(b"helloworld");

        let old_instance = Instance::from("old");
        let new_instance = Instance::from("new");

        let semaphore = Arc::new(Semaphore::new(0));

        let mut storage = DarkLaunchStorage::new(
            WriteSemaphoreStorage::new(MemoryStorage::new(), semaphore.clone()),
            WriteSemaphoreStorage::new(MemoryStorage::new(), semaphore.clone()),
            vec![new_instance.name.clone()],
            true,
            "test",
        );

        storage.ensure_instance(&old_instance, DriverState::default());
        storage.ensure_instance(&new_instance, DriverState::default());

        // Write `content1` to the "old" instance. It should show up under the old instance name
        // on both old and new backends. (Will be tested below.)
        let mut attempt1 = storage
            .begin_write_blob(
                old_instance.clone(),
                content1.digest,
                DriverState::default(),
            )
            .await
            .unwrap();
        attempt1.write(content1.bytes).await.unwrap();
        attempt1.commit().await.unwrap();

        acquire_and_forget(&semaphore, 2, Duration::from_secs(2)).await;

        // Write `content2` to the "new" instance. It should show up under the new instance name
        // also on both old and new backends.
        let mut attempt2 = storage
            .begin_write_blob(
                new_instance.clone(),
                content2.digest,
                DriverState::default(),
            )
            .await
            .unwrap();
        attempt2.write(content2.bytes).await.unwrap();
        attempt2.commit().await.unwrap();

        acquire_and_forget(&semaphore, 2, Duration::from_secs(2)).await;

        let (old_storage, new_storage) = {
            let (s1, s2) = storage.into_inner();
            (s1.into_inner(), s2.into_inner())
        };

        // Old instance on old storage should only have received `content1` (so `content2` is missing).
        assert_missing_blobs(
            &old_storage,
            &old_instance,
            vec![content1.digest, content2.digest],
            vec![content2.digest],
        )
        .await;

        // Old instance on new storage should have received `content1` as well (so `content2` is
        // missing). This is due to "write to secondary" being true.
        assert_missing_blobs(
            &new_storage,
            &old_instance,
            vec![content1.digest, content2.digest],
            vec![content2.digest],
        )
        .await;

        // New instance on new storage should have received `content2` (so `content1` is missing`).
        assert_missing_blobs(
            &new_storage,
            &new_instance,
            vec![content1.digest, content2.digest],
            vec![content1.digest],
        )
        .await;

        // New instance on old storage should have also received `content2` (so `content1`
        // is missing).
        assert_missing_blobs(
            &old_storage,
            &new_instance,
            vec![content1.digest, content2.digest],
            vec![content1.digest],
        )
        .await;
    }

    #[tokio::test]
    async fn dark_launch_with_secondary_disabled_writes_only_one_backend() {
        let content1 = TestData::from_static(b"foobar");
        let content2 = TestData::from_static(b"helloworld");

        let old_instance = Instance::from("old");
        let new_instance = Instance::from("new");

        let semaphore = Arc::new(Semaphore::new(0));

        let mut storage = DarkLaunchStorage::new(
            WriteSemaphoreStorage::new(MemoryStorage::new(), semaphore.clone()),
            WriteSemaphoreStorage::new(MemoryStorage::new(), semaphore.clone()),
            vec![new_instance.name.clone()],
            false, // note: do not write to secondary storage
            "test",
        );

        storage.ensure_instance(&old_instance, DriverState::default());
        storage.ensure_instance(&new_instance, DriverState::default());

        // Write `content1` to the "old" instance. It should show up under the old instance name
        // on the old backend only. (Will be tested below.)
        let mut attempt1 = storage
            .begin_write_blob(
                old_instance.clone(),
                content1.digest,
                DriverState::default(),
            )
            .await
            .unwrap();
        attempt1.write(content1.bytes).await.unwrap();
        attempt1.commit().await.unwrap();

        acquire_and_forget(&semaphore, 1, Duration::from_secs(2)).await;

        // Write `content2` to the "new" instance. It should show up under the new instance name
        // only on the new backend. (Will be tested below.)
        let mut attempt2 = storage
            .begin_write_blob(
                new_instance.clone(),
                content2.digest,
                DriverState::default(),
            )
            .await
            .unwrap();
        attempt2.write(content2.bytes).await.unwrap();
        attempt2.commit().await.unwrap();

        acquire_and_forget(&semaphore, 1, Duration::from_secs(2)).await;

        let (old_storage, new_storage) = {
            let (s1, s2) = storage.into_inner();
            (s1.into_inner(), s2.into_inner())
        };

        // Old instance on old storage should only have received `content1` (so `content2` is missing).
        assert_missing_blobs(
            &old_storage,
            &old_instance,
            vec![content1.digest, content2.digest],
            vec![content2.digest],
        )
        .await;

        // Old instance on new storage should not have received `content1`.
        // This is due to "write to secondary" being false.
        assert_missing_blobs(
            &new_storage,
            &old_instance,
            vec![content1.digest, content2.digest],
            vec![content1.digest, content2.digest],
        )
        .await;

        // New instance on new storage should have received `content2` (so `content1` is missing`).
        assert_missing_blobs(
            &new_storage,
            &new_instance,
            vec![content1.digest, content2.digest],
            vec![content1.digest],
        )
        .await;

        // Old instance on new storage should not have received `content2`.
        // This is due to "write to secondary" being false.
        assert_missing_blobs(
            &old_storage,
            &new_instance,
            vec![content1.digest, content2.digest],
            vec![content1.digest, content2.digest],
        )
        .await;
    }

    #[tokio::test]
    async fn dark_launch_storage_reads_from_only_one_backend() {
        let content1 = TestData::from_static(b"foobar");
        let content2 = TestData::from_static(b"helloworld");

        let instance1 = Instance::from("left");
        let instance2 = Instance::from("right");

        let mut storage = DarkLaunchStorage::new(
            CountMethodCallsStorage::new(MemoryStorage::new()),
            CountMethodCallsStorage::new(MemoryStorage::new()),
            vec![instance2.name.clone()],
            true,
            "test",
        );

        storage.ensure_instance(&instance1, DriverState::default());
        storage.ensure_instance(&instance2, DriverState::default());

        let mut attempt1 = storage
            .begin_write_blob(instance1.clone(), content1.digest, DriverState::default())
            .await
            .unwrap();
        attempt1.write(content1.bytes).await.unwrap();
        attempt1.commit().await.unwrap();

        let mut attempt2 = storage
            .begin_write_blob(instance2.clone(), content2.digest, DriverState::default())
            .await
            .unwrap();
        attempt2.write(content2.bytes).await.unwrap();
        attempt2.commit().await.unwrap();

        let stream1 = storage
            .read_blob(
                instance1.clone(),
                content1.digest,
                1024,
                None,
                None,
                DriverState::default(),
            )
            .await
            .unwrap()
            .unwrap();
        let _ = consolidate_stream(stream1).await.unwrap();

        let stream2 = storage
            .read_blob(
                instance2.clone(),
                content2.digest,
                1024,
                None,
                None,
                DriverState::default(),
            )
            .await
            .unwrap()
            .unwrap();
        let _ = consolidate_stream(stream2).await.unwrap();

        let (storage1, storage2) = storage.into_inner();

        assert_eq!(storage1.find_missing_blobs_count.load(Ordering::SeqCst), 0);
        assert_eq!(storage1.read_count.load(Ordering::SeqCst), 1);
        assert_eq!(storage1.write_count.load(Ordering::SeqCst), 2);

        assert_eq!(storage2.find_missing_blobs_count.load(Ordering::SeqCst), 0);
        assert_eq!(storage2.read_count.load(Ordering::SeqCst), 1);
        assert_eq!(storage2.write_count.load(Ordering::SeqCst), 2);
    }
}
