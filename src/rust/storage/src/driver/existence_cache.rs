// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::num::NonZeroUsize;
use std::sync::Arc;

use async_trait::async_trait;
use lasso::{Spur, ThreadedRodeo};
use lru::LruCache;
use parking_lot::RwLock;

use crate::driver::{
    BlobStorage, BoxReadStream, DriverState, Instance, StorageError, StreamingWriteError,
    WriteAttemptOps,
};
use crate::Digest;

/// A `BlobStorage` that speeds up `find_missing_blobs` RPCs by caching the existence of blobs
/// found in an underlying storage backend.
pub struct ExistenceCacheStorage<S> {
    instance_interns: ThreadedRodeo,
    cache: Arc<RwLock<LruCache<(Spur, Digest), ()>>>,
    underlying: S,
}

impl<S> ExistenceCacheStorage<S> {
    /// Return the intern'ed key for an instance name.
    fn get_key_for_instance(&self, instance: &Instance) -> Spur {
        self.instance_interns.get_or_intern(&instance.name)
    }
}

#[async_trait]
impl<S> BlobStorage for ExistenceCacheStorage<S>
where
    S: BlobStorage + Send + Sync + 'static,
{
    async fn find_missing_blobs(
        &self,
        instance: Instance,
        digests: Vec<Digest>,
        state: DriverState,
    ) -> Result<Vec<Digest>, StorageError> {
        let instance_key = self.get_key_for_instance(&instance);

        let unknown_digests = {
            let cache = self.cache.read();

            digests
                .into_iter()
                .map(|digest| (instance_key, digest))
                .filter_map(|cache_key| {
                    if cache.contains(&cache_key) {
                        None
                    } else {
                        Some(cache_key.1)
                    }
                })
                .collect::<Vec<_>>()
        };

        if unknown_digests.is_empty() {
            return Ok(Vec::new());
        }

        let missing_digests = self
            .underlying
            .find_missing_blobs(instance, unknown_digests.clone(), state)
            .await?;

        let present_digests = unknown_digests
            .iter()
            .filter(|digest| !missing_digests.contains(digest))
            .collect::<Vec<_>>();

        if !present_digests.is_empty() {
            let mut cache = self.cache.write();
            for present_digest in present_digests {
                cache.put((instance_key, *present_digest), ());
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
    ) -> Result<Box<dyn WriteAttemptOps + Send + Sync>, StreamingWriteError> {
        self.underlying
            .begin_write_blob(instance, digest, state)
            .await
    }
}

impl<S> ExistenceCacheStorage<S>
where
    S: BlobStorage + Send + Sync + 'static,
{
    pub fn new(max_lru_entries: NonZeroUsize, underlying: S) -> Self {
        ExistenceCacheStorage {
            instance_interns: ThreadedRodeo::new(),
            cache: Arc::new(RwLock::new(LruCache::new(max_lru_entries))),
            underlying,
        }
    }
}

#[cfg(test)]
mod tests {
    use std::num::NonZeroUsize;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::sync::Arc;

    use async_trait::async_trait;

    use super::ExistenceCacheStorage;
    use crate::driver::{
        BlobStorage, BoxReadStream, DriverState, Instance, StorageError, StreamingWriteError,
        WriteAttemptOps,
    };
    use crate::testutil::TestData;
    use crate::Digest;

    struct CountFindMissingBlobsStorage {
        count: Arc<AtomicUsize>,
    }

    #[async_trait]
    impl BlobStorage for CountFindMissingBlobsStorage {
        async fn find_missing_blobs(
            &self,
            _instance: Instance,
            _digests: Vec<Digest>,
            _state: DriverState,
        ) -> Result<Vec<Digest>, StorageError> {
            self.count.fetch_add(1, Ordering::SeqCst);
            Ok(Vec::new())
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
            unimplemented!()
        }

        async fn begin_write_blob(
            &self,
            _instance: Instance,
            _digest: Digest,
            _state: DriverState,
        ) -> Result<Box<dyn WriteAttemptOps + Send + Sync>, StreamingWriteError> {
            unimplemented!()
        }
    }

    #[tokio::test]
    async fn caches_present_digests() {
        let calls_count = Arc::new(AtomicUsize::new(0));

        let storage = ExistenceCacheStorage::new(
            NonZeroUsize::new(256).unwrap(),
            CountFindMissingBlobsStorage {
                count: calls_count.clone(),
            },
        );

        let instance = Instance::from("main");
        let content = TestData::from_static(b"foobar");

        // First call should call the underlying storage.
        assert_eq!(0, calls_count.load(Ordering::SeqCst));
        let missing_digests = storage
            .find_missing_blobs(
                instance.clone(),
                vec![content.digest],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert!(missing_digests.is_empty());
        assert_eq!(1, calls_count.load(Ordering::SeqCst));

        // Second call should not.
        let missing_digests = storage
            .find_missing_blobs(
                instance.clone(),
                vec![content.digest],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert!(missing_digests.is_empty());
        assert_eq!(1, calls_count.load(Ordering::SeqCst));

        let content2 = TestData::from_static(b"xyzzy");

        // Third call with both digests should call the underlying storage since `digest2`
        // is not cached yet.
        let missing_digests = storage
            .find_missing_blobs(
                instance.clone(),
                vec![content.digest, content2.digest],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert!(missing_digests.is_empty());
        assert_eq!(2, calls_count.load(Ordering::SeqCst));

        // Fourth call with both digess should not call the underlying storage. (Both cached.)
        let missing_digests = storage
            .find_missing_blobs(
                instance,
                vec![content.digest, content2.digest],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert!(missing_digests.is_empty());
        assert_eq!(2, calls_count.load(Ordering::SeqCst));
    }
}
