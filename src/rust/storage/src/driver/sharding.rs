// Copyright 2022 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::collections::{HashMap, HashSet};
use std::fmt::Debug;
use std::hash::Hash;
use std::num::NonZeroUsize;

use async_trait::async_trait;
use bytes::Bytes;
use consistent_hash_ring::{Ring, RingBuilder};
use futures::stream::FuturesUnordered;
use futures::{future, FutureExt, StreamExt};

use crate::driver::{
    BlobStorage, BoxReadStream, DriverState, Instance, StorageError, StreamingWriteError,
    WriteAttemptOps,
};
use crate::Digest;

type BoxBlobStorage = Box<dyn BlobStorage + Send + Sync + 'static>;

/// Number of virtual nodes in the hash ring used for sharding.
const RING_SIZE: usize = 10240;

/// Shards digests over N storage shards.
pub struct ShardingStorage<T> {
    ring: Ring<T>,
    shard_key_to_storage: HashMap<T, BoxBlobStorage>,
    key_replicas: NonZeroUsize,
    purpose: &'static str,
    _shard_descriptions: HashMap<T, String>,
}

/// Distribute queries over a set of shards using a consistent-hash algorithm.
///
/// The `ShardingStorage` driver distributes a queries over a given set of shards using
/// a consistent-hash algorithm to distribute digests around a hash ring. (Node and key placement
/// are handled by the `consistent_hash_ring` crate.)
///
/// To ensure high availability, reads and writes involve a chain of shards to which a key is
/// assigned and not just that key's primary shard. Thus:
///
/// - Reads are sent to all shards for a digest with the first shard returning content for that
/// digest winning. Unavailable shards are skipped; other errors are surfaced. A digest will
/// only be reported as missing if there was at least one available shard.
///
/// - Writes are distributed to all shards for a digest. Each chunk on the write stream is
/// written in lockstep. If any shard errors, it is removed from the write attempt in order
/// to avoid passing that error back to the API client.
///
/// Note: This driver intentionally favors high availability over strong consistency and so
/// the driver will not attempt to retry failed writes etc.
impl<T> ShardingStorage<T>
where
    T: Hash + Eq + Copy + Send + Sync + 'static,
{
    /// Construct a `ShardingStorage` from the given shards.
    ///
    /// `key_replicas` is the number of shards to check for a key including the primary shard.
    /// If a shard is unavailable, then the driver will fallback to subsequent shards. Writes are
    /// replicated to all of the fallback shards.
    pub fn new(
        shards: Vec<(T, BoxBlobStorage)>,
        key_replicas: NonZeroUsize,
        purpose: &'static str,
        shard_descriptions: HashMap<T, String>,
    ) -> Self {
        let mut ring_builder = RingBuilder::default().vnodes(RING_SIZE);

        let mut shard_key_to_storage = HashMap::new();
        for (key, storage) in shards {
            shard_key_to_storage.insert(key, storage);
            ring_builder = ring_builder.node(key);
        }

        Self {
            ring: ring_builder.build(),
            shard_key_to_storage,
            key_replicas,
            purpose,
            _shard_descriptions: shard_descriptions,
        }
    }

    fn storages_for_digest(&self, digest: Digest) -> impl Iterator<Item = &BoxBlobStorage> {
        self.ring
            .replicas(digest)
            .take(self.key_replicas.into())
            .flat_map(|k| self.shard_key_to_storage.get(k))
    }

    /// Return a vector with each shard ID and its applicable storage driver.
    ///
    /// Note: The ordering of the returned vector is not stable across process invocations
    /// due to hash randomization in `HashMap`. If you need a consistent order, then sort
    /// the vector as necessary.
    #[cfg(test)]
    pub fn into_inner(self) -> Vec<(T, BoxBlobStorage)> {
        self.shard_key_to_storage.into_iter().collect()
    }
}

#[async_trait]
impl<T> BlobStorage for ShardingStorage<T>
where
    T: Hash + Eq + Copy + Debug + Send + Sync + 'static,
{
    async fn find_missing_blobs(
        &self,
        instance: Instance,
        digests: Vec<Digest>,
        state: DriverState,
    ) -> Result<Vec<Digest>, StorageError> {
        // Partition the digests by the storage driver to use.
        let mut storage_to_digest: HashMap<T, HashSet<Digest>> = HashMap::new();
        for digest in &digests {
            let replica_keys = self.ring.replicas(digest).take(self.key_replicas.into());
            for replica_key in replica_keys {
                storage_to_digest
                    .entry(*replica_key)
                    .or_insert_with(HashSet::new)
                    .insert(*digest);
            }
        }

        let futures = storage_to_digest.iter().map(|(key, digests)| {
            let digests = {
                let mut xs: Vec<_> = digests.iter().copied().collect();
                xs.sort();
                xs
            };
            let storage = self
                .shard_key_to_storage
                .get(key)
                .expect("lookup shard in shard map");
            storage
                .find_missing_blobs(instance.clone(), digests, state.clone())
                .map(|r| (*key, r))
                .boxed()
        });

        let results = future::join_all(futures).await;

        let mut result_by_digest: HashMap<Digest, Option<bool>> =
            digests.iter().map(|d| (*d, None)).collect();
        for result in &results {
            match result {
                (shard_key, Ok(missing_digests)) => {
                    let missing_digests = missing_digests.iter().collect::<HashSet<_>>();
                    let digests_for_shard_key = storage_to_digest
                        .get(shard_key)
                        .expect("shard key must be present in storage_to_digest mapping");
                    for digest in digests_for_shard_key {
                        let is_present_here = !missing_digests.contains(digest);
                        let digest_result = result_by_digest
                            .get_mut(digest)
                            .expect("Entry for digest in shard map");
                        match digest_result {
                            Some(is_present_anywhere) => {
                                // If the digest is not yet marked present but is present from this
                                // query, then mark it present.
                                if !*is_present_anywhere && is_present_here {
                                    *digest_result = Some(true);
                                }
                            }
                            None => *digest_result = Some(is_present_here),
                        }
                    }
                }

                (shard_key, Err(err)) => {
                    log::error!("find_missing_blobs failed on shard {:?}: {err}", shard_key);
                    if matches!(err, StorageError::Unavailable(_)) {
                        metrics::counter!(
                            "toolchain_storage_shard_unavailable_total",
                            1,
                            "driver" => "sharding",
                            "purpose" => self.purpose,
                        );
                    }
                }
            }
        }

        // Error as unavailable if not all digests received an answer.
        if result_by_digest.iter().any(|(_, r)| r.is_none()) {
            return Err(StorageError::Unavailable(
                "Not enough shards were available to answer query.".to_string(),
            ));
        }

        let missing_digests = result_by_digest
            .into_iter()
            .filter(|(_, r)| matches!(r, Some(false)))
            .map(|(digest, _)| digest)
            .collect::<Vec<_>>();

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
        let mut results_stream = self
            .storages_for_digest(digest)
            .map(|storage| {
                storage
                    .read_blob(
                        instance.clone(),
                        digest,
                        max_batch_size,
                        read_offset,
                        read_limit,
                        state.clone(),
                    )
                    .boxed()
            })
            .collect::<FuturesUnordered<_>>();

        let mut at_least_one_available = false;
        while let Some(result) = results_stream.next().await {
            match result {
                Ok(Some(stream)) => return Ok(Some(stream)),
                Ok(None) => {
                    // Skip missing results in hope it will be found in another shard.
                    at_least_one_available = true;
                    continue;
                }
                Err(err @ StorageError::Unavailable(_)) => {
                    log::error!("Skipping unavailable sharding during read: {:?}", err);

                    metrics::counter!(
                        "toolchain_storage_shard_unavailable_total",
                        1,
                        "driver" => "sharding",
                        "purpose" => self.purpose,
                    );
                    continue;
                }
                Err(err) => return Err(err),
            }
        }

        // If the digest was not found in any available shard, then it is missing.
        // If there were no available shards, then error.
        if at_least_one_available {
            Ok(None)
        } else {
            Err(StorageError::Unavailable(
                "No shards were available to answer read query.".to_string(),
            ))
        }
    }

    async fn begin_write_blob(
        &self,
        instance: Instance,
        digest: Digest,
        state: DriverState,
    ) -> Result<Box<dyn WriteAttemptOps + Send + Sync + 'static>, StreamingWriteError> {
        let attempt_results = futures::future::join_all(
            self.storages_for_digest(digest)
                .map(|storage| {
                    storage
                        .begin_write_blob(instance.clone(), digest, state.clone())
                        .boxed()
                })
                .collect::<Vec<_>>(),
        )
        .await;

        if attempt_results
            .iter()
            .all(|r| matches!(r, Err(StreamingWriteError::AlreadyExists)))
        {
            // We don't need to write to any destinations.
            return Err(StreamingWriteError::AlreadyExists);
        }

        let attempts = attempt_results
            .into_iter()
            .filter_map(|r| match r {
                Ok(attempt) => Some(attempt),
                Err(StreamingWriteError::AlreadyExists) => {
                    // We don't need to write to this destination, but we do need to write to at
                    // least one other destination. Just filter it out.
                    None
                }
                Err(err) => {
                    log::error!("Creation of write attempt failed: {:?}", err);
                    metrics::counter!(
                        "toolchain_storage_sharding_write_error_total",
                        1,
                        "driver" => "sharding",
                        "purpose" => self.purpose,
                    );
                    None
                }
            })
            .collect::<Vec<_>>();

        Ok(Box::new(WriteAttempt {
            attempts,
            purpose: self.purpose,
        }))
    }

    fn ensure_instance(&mut self, instance: &Instance, state: DriverState) {
        for shard in self.shard_key_to_storage.values_mut() {
            shard.ensure_instance(instance, state.clone());
        }
    }
}

struct WriteAttempt {
    attempts: Vec<Box<dyn WriteAttemptOps + Send + Sync>>,
    purpose: &'static str,
}

#[async_trait]
impl WriteAttemptOps for WriteAttempt {
    async fn write(&mut self, batch: Bytes) -> Result<(), StreamingWriteError> {
        let mut write_futures = Vec::new();
        for attempt in &mut self.attempts {
            let write_fut = attempt.write(batch.clone()).boxed();
            write_futures.push(write_fut);
        }

        let results = futures::future::join_all(write_futures).await;

        let mut indices_to_remove = Vec::new();
        for (i, result) in results.into_iter().enumerate() {
            if result.is_err() {
                // Ignore errors from failed shards by removing this shard's write attempt
                // so subsequent writes (and commit) do not operate on this shard.
                log::error!(
                    "Failed to write chunk to shard (shard will be dropped from this write): {:?}",
                    result
                );

                metrics::counter!(
                    "toolchain_storage_sharding_write_error_total",
                    1,
                    "driver" => "sharding",
                    "purpose" => self.purpose,
                );
                indices_to_remove.push(i);
            }
        }

        for i in indices_to_remove.into_iter().rev() {
            self.attempts.remove(i);
        }

        Ok(())
    }

    async fn commit(self: Box<Self>) -> Result<(), StreamingWriteError> {
        let purpose = self.purpose;

        let commit_futures = self
            .attempts
            .into_iter()
            .map(|attempt| attempt.commit().boxed());

        let results = futures::future::join_all(commit_futures).await;
        let mut at_least_one_success = false;
        let mut last_error: Option<StreamingWriteError> = None;

        for result in results {
            match result {
                Ok(()) => at_least_one_success = true,
                Err(err) => {
                    log::error!("Failed to commit write to shard: {:?}", &err);

                    metrics::counter!(
                        "toolchain_storage_sharding_write_error_total",
                        1,
                        "driver" => "sharding",
                        "purpose" => purpose,
                    );
                    last_error = Some(err);
                }
            }
        }

        if at_least_one_success {
            Ok(())
        } else {
            match last_error {
                Some(err) => Err(err),
                None => Err(StorageError::Unavailable(
                    "All shards returned errors during write.".to_owned(),
                )
                .into()),
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use std::collections::HashMap;
    use std::fmt::Write;
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::sync::Arc;
    use std::time::Duration;

    use async_trait::async_trait;
    use bytes::BytesMut;
    use tokio::sync::Semaphore;

    use crate::bytes::consolidate_stream;
    use crate::driver::{
        BlobStorage, BoxReadStream, DriverState, Instance, MemoryStorage, ShardingStorage,
        StorageError, StreamingWriteError, WriteAttemptOps,
    };
    use crate::testutil::{AlwaysExistsStorage, WriteSemaphoreStorage};
    use crate::Digest;

    async fn acquire_and_forget(semaphore: &Semaphore, n: u32, timeout: Duration) {
        let permits = tokio::time::timeout(timeout, semaphore.acquire_many(n))
            .await
            .unwrap()
            .unwrap();
        permits.forget();
    }

    #[tokio::test]
    async fn basic_sharding_works() {
        let mut storage1 = MemoryStorage::new();
        let mut storage2 = MemoryStorage::new();
        let instance = Instance::from("main");
        storage1.ensure_instance(&instance, DriverState::default());
        storage2.ensure_instance(&instance, DriverState::default());

        let storage: ShardingStorage<usize> = ShardingStorage::new(
            vec![(0, Box::new(storage1)), (1, Box::new(storage2))],
            1.try_into().unwrap(),
            "test",
            HashMap::default(),
        );

        let content1 = {
            let mut buf = BytesMut::new();
            buf.write_str("foobar").unwrap();
            buf.freeze()
        };
        let digest1 = Digest::of_bytes(&content1).unwrap();

        let content2 = {
            let mut buf = BytesMut::new();
            buf.write_str("barfoo").unwrap();
            buf.freeze()
        };
        let digest2 = Digest::of_bytes(&content2).unwrap();

        let mut attempt = storage
            .begin_write_blob(instance.clone(), digest1, DriverState::default())
            .await
            .unwrap();
        attempt.write(content1.clone()).await.unwrap();
        attempt.commit().await.unwrap();

        let mut attempt = storage
            .begin_write_blob(instance.clone(), digest2, DriverState::default())
            .await
            .unwrap();
        attempt.write(content2.clone()).await.unwrap();
        attempt.commit().await.unwrap();

        let child_storages = {
            // Note: The order of storage drivers in the returned vector is not consistent
            // across runs due to hash randomization for HashMap. Thus, sort the vector
            // into consistent order.
            let mut storages = storage.into_inner();
            storages.sort_by_key(|(id, _)| *id);
            storages.into_iter().map(|(_, s)| s).collect::<Vec<_>>()
        };

        let missing_blobs = child_storages[0]
            .find_missing_blobs(
                instance.clone(),
                vec![digest1, digest2],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert_eq!(missing_blobs, vec![digest2]);

        let missing_blobs = child_storages[1]
            .find_missing_blobs(
                instance.clone(),
                vec![digest1, digest2],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert_eq!(missing_blobs, vec![digest1]);
    }

    #[tokio::test]
    async fn basic_replicated_writes_are_successful() {
        let semaphore = Arc::new(Semaphore::new(0));
        let mut storage1 = WriteSemaphoreStorage::new(MemoryStorage::new(), semaphore.clone());
        let mut storage2 = WriteSemaphoreStorage::new(MemoryStorage::new(), semaphore.clone());
        let mut storage3 = WriteSemaphoreStorage::new(MemoryStorage::new(), semaphore.clone());
        let instance = Instance::from("main");
        storage1.ensure_instance(&instance, DriverState::default());
        storage2.ensure_instance(&instance, DriverState::default());
        storage3.ensure_instance(&instance, DriverState::default());

        let storage: ShardingStorage<usize> = ShardingStorage::new(
            vec![
                (0, Box::new(storage1)),
                (1, Box::new(storage2)),
                (2, Box::new(storage3)),
            ],
            2.try_into().unwrap(),
            "test",
            HashMap::default(),
        );

        let content1 = {
            let mut buf = BytesMut::new();
            buf.write_str("foobar").unwrap();
            buf.freeze()
        };
        let digest1 = Digest::of_bytes(&content1).unwrap();

        let content2 = {
            let mut buf = BytesMut::new();
            buf.write_str("barfoo").unwrap();
            buf.freeze()
        };
        let digest2 = Digest::of_bytes(&content2).unwrap();

        let mut attempt = storage
            .begin_write_blob(instance.clone(), digest1, DriverState::default())
            .await
            .unwrap();
        attempt.write(content1.clone()).await.unwrap();
        attempt.commit().await.unwrap();

        acquire_and_forget(&semaphore, 2, Duration::from_secs(1)).await;

        let mut attempt = storage
            .begin_write_blob(instance.clone(), digest2, DriverState::default())
            .await
            .unwrap();
        attempt.write(content2.clone()).await.unwrap();
        attempt.commit().await.unwrap();

        acquire_and_forget(&semaphore, 2, Duration::from_secs(1)).await;

        let child_storages = {
            // Note: The order of storage drivers in the returned vector is not consistent
            // across runs due to hash randomization for HashMap. Thus, sort the vector
            // into consistent order.
            let mut storages = storage.into_inner();
            storages.sort_by_key(|(id, _)| *id);
            storages.into_iter().map(|(_, s)| s).collect::<Vec<_>>()
        };

        // The two digests (`digest1` and `digest2`) should each only end up on 2 of 3 shards
        // as follows:
        //
        // Shard 1: Both
        // Shard 2: digest2 only
        // Shard 3: digest1 only

        let missing_blobs = child_storages[0]
            .find_missing_blobs(
                instance.clone(),
                vec![digest1, digest2],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert_eq!(missing_blobs, vec![]);

        let missing_blobs = child_storages[1]
            .find_missing_blobs(
                instance.clone(),
                vec![digest1, digest2],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert_eq!(missing_blobs, vec![digest1]);

        let missing_blobs = child_storages[2]
            .find_missing_blobs(
                instance.clone(),
                vec![digest1, digest2],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert_eq!(missing_blobs, vec![digest2]);
    }

    struct FailGatedStorage<S> {
        inner: S,
        respond_unavailable: Arc<AtomicBool>,
    }

    impl<S> FailGatedStorage<S> {
        pub fn new(inner: S, respond_unavailable: &Arc<AtomicBool>) -> Self {
            Self {
                inner,
                respond_unavailable: respond_unavailable.clone(),
            }
        }
    }

    #[async_trait]
    impl<S> BlobStorage for FailGatedStorage<S>
    where
        S: BlobStorage + Send + Sync + 'static,
    {
        async fn find_missing_blobs(
            &self,
            instance: Instance,
            digests: Vec<Digest>,
            state: DriverState,
        ) -> Result<Vec<Digest>, StorageError> {
            if self.respond_unavailable.load(Ordering::SeqCst) {
                Err(StorageError::Unavailable("UNAVAILABLE".to_string()))
            } else {
                self.inner
                    .find_missing_blobs(instance, digests, state)
                    .await
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
            if self.respond_unavailable.load(Ordering::SeqCst) {
                Err(StorageError::Unavailable("UNAVAILABLE".to_string()))
            } else {
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
        }

        async fn begin_write_blob(
            &self,
            instance: Instance,
            digest: Digest,
            state: DriverState,
        ) -> Result<Box<dyn WriteAttemptOps + Send + Sync + 'static>, StreamingWriteError> {
            if self.respond_unavailable.load(Ordering::SeqCst) {
                Err(StorageError::Unavailable("UNAVAILABLE".to_string()).into())
            } else {
                self.inner.begin_write_blob(instance, digest, state).await
            }
        }

        fn ensure_instance(&mut self, instance: &Instance, state: DriverState) {
            self.inner.ensure_instance(instance, state);
        }
    }

    #[tokio::test]
    async fn sharding_falls_back_to_replicas_without_errors() {
        let shard1_unavailable = Arc::new(AtomicBool::new(false));
        let shard2_unavailable = Arc::new(AtomicBool::new(false));

        let mut storage1 = FailGatedStorage::new(MemoryStorage::new(), &shard1_unavailable);
        let mut storage2 = FailGatedStorage::new(MemoryStorage::new(), &shard2_unavailable);
        let instance = Instance::from("main");
        storage1.ensure_instance(&instance, DriverState::default());
        storage2.ensure_instance(&instance, DriverState::default());

        let storage: ShardingStorage<usize> = ShardingStorage::new(
            vec![(0, Box::new(storage1)), (1, Box::new(storage2))],
            2.try_into().unwrap(),
            "test",
            HashMap::default(),
        );

        let content1 = {
            let mut buf = BytesMut::new();
            buf.write_str("foobar").unwrap();
            buf.freeze()
        };
        let digest1 = Digest::of_bytes(&content1).unwrap();

        let mut attempt = storage
            .begin_write_blob(instance.clone(), digest1, DriverState::default())
            .await
            .unwrap();
        attempt.write(content1.clone()).await.unwrap();
        attempt.commit().await.unwrap();

        //
        // Test that find_missing_blobs works regardless of availability.
        //

        shard1_unavailable.store(false, Ordering::SeqCst);
        shard2_unavailable.store(false, Ordering::SeqCst);
        let result = storage
            .find_missing_blobs(instance.clone(), vec![digest1], DriverState::default())
            .await;
        assert_eq!(result, Ok(vec![]));

        shard1_unavailable.store(true, Ordering::SeqCst);
        shard2_unavailable.store(false, Ordering::SeqCst);
        let result = storage
            .find_missing_blobs(instance.clone(), vec![digest1], DriverState::default())
            .await;
        assert_eq!(result, Ok(vec![]));

        shard1_unavailable.store(false, Ordering::SeqCst);
        shard2_unavailable.store(true, Ordering::SeqCst);
        let result = storage
            .find_missing_blobs(instance.clone(), vec![digest1], DriverState::default())
            .await;
        assert_eq!(result, Ok(vec![]));

        shard1_unavailable.store(true, Ordering::SeqCst);
        shard2_unavailable.store(true, Ordering::SeqCst);
        let result = storage
            .find_missing_blobs(instance.clone(), vec![digest1], DriverState::default())
            .await;
        assert!(matches!(result, Err(StorageError::Unavailable(_))));

        //
        // Test that reading the blob works regardless of availability except if all
        // shards are unavailable.
        //
        shard1_unavailable.store(false, Ordering::SeqCst);
        shard2_unavailable.store(false, Ordering::SeqCst);
        let stream = storage
            .read_blob(
                instance.clone(),
                digest1,
                3,
                None,
                None,
                DriverState::default(),
            )
            .await
            .unwrap()
            .unwrap();
        let actual_content = consolidate_stream(stream).await.unwrap();
        assert_eq!(actual_content, content1);

        shard1_unavailable.store(true, Ordering::SeqCst);
        shard2_unavailable.store(false, Ordering::SeqCst);
        let stream = storage
            .read_blob(
                instance.clone(),
                digest1,
                3,
                None,
                None,
                DriverState::default(),
            )
            .await
            .unwrap()
            .unwrap();
        let actual_content = consolidate_stream(stream).await.unwrap();
        assert_eq!(actual_content, content1);

        shard1_unavailable.store(false, Ordering::SeqCst);
        shard2_unavailable.store(true, Ordering::SeqCst);
        let stream = storage
            .read_blob(
                instance.clone(),
                digest1,
                3,
                None,
                None,
                DriverState::default(),
            )
            .await
            .unwrap()
            .unwrap();
        let actual_content = consolidate_stream(stream).await.unwrap();
        assert_eq!(actual_content, content1);

        shard1_unavailable.store(true, Ordering::SeqCst);
        shard2_unavailable.store(true, Ordering::SeqCst);
        let result = storage
            .read_blob(
                instance.clone(),
                digest1,
                3,
                None,
                None,
                DriverState::default(),
            )
            .await;
        assert!(matches!(result, Err(StorageError::Unavailable(_))));
    }

    #[tokio::test]
    async fn handles_existing_blobs_all() {
        let storage1 = AlwaysExistsStorage;
        let storage2 = AlwaysExistsStorage;
        let instance = Instance::from("main");

        let storage: ShardingStorage<usize> = ShardingStorage::new(
            vec![(0, Box::new(storage1)), (1, Box::new(storage2))],
            1.try_into().unwrap(),
            "test",
            HashMap::default(),
        );

        let content1 = {
            let mut buf = BytesMut::new();
            buf.write_str("foobar").unwrap();
            buf.freeze()
        };
        let digest1 = Digest::of_bytes(&content1).unwrap();

        // If all storage backends return `AlreadyExists`, we should immediately exit and
        // indicate that the value already exists, without actually writing it.
        assert_eq!(
            StreamingWriteError::AlreadyExists,
            storage
                .begin_write_blob(instance.clone(), digest1, DriverState::default())
                .await
                .err()
                .unwrap()
        )
    }

    #[tokio::test]
    async fn handles_existing_blobs_partial() {
        let mut storage1 = MemoryStorage::new();
        let storage2 = AlwaysExistsStorage;
        let instance = Instance::from("main");
        storage1.ensure_instance(&instance, DriverState::default());

        let storage: ShardingStorage<usize> = ShardingStorage::new(
            vec![(0, Box::new(storage1)), (1, Box::new(storage2))],
            1.try_into().unwrap(),
            "test",
            HashMap::default(),
        );

        let content1 = {
            let mut buf = BytesMut::new();
            buf.write_str("foobar").unwrap();
            buf.freeze()
        };
        let digest1 = Digest::of_bytes(&content1).unwrap();

        // If only one storage backend returns `AlreadyExists`, we should succeed in writing it to
        // the other one.
        let mut attempt = storage
            .begin_write_blob(instance.clone(), digest1, DriverState::default())
            .await
            .unwrap();
        attempt.write(content1.clone()).await.unwrap();
        attempt.commit().await.unwrap();
    }
}
