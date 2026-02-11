// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use async_trait::async_trait;
use bytes::Bytes;
use futures::future;
use itertools::Itertools;
use redis::FromRedisValue;

use super::common::{redis_query, ConnectionGetter};
use crate::driver::redis::common::redis_pipeline;
use crate::driver::small::SmallBlobStorage;
use crate::driver::{DriverState, Instance, StorageError};
use crate::Digest;

/// Label used for metrics.
const DRIVER_LABEL: &str = "redis_direct";

/// Number of digests per batch for find_missing_blobs.
const FIND_MISSING_BLOBS_BATCH_SIZE: usize = 1000;

/// Stores blobs in Redis using a "direct" encoding where blobs are stored in a single key. This
/// is intended for blobs of small size. Supports multiple instances.
///
/// Keys have the format: INSTANCE-DIGEST_HASH-DIGEST_SIZE
#[derive(Clone)]
pub struct RedisDirectStorage<C>
where
    C: ConnectionGetter + Clone + Send + Sync,
{
    conn: C,
    prefix: String,
}

#[async_trait]
impl<C> SmallBlobStorage for RedisDirectStorage<C>
where
    C: ConnectionGetter + Clone + Send + Sync + 'static,
{
    async fn find_missing_blobs(
        &self,
        instance: Instance,
        digests: Vec<Digest>,
        _state: DriverState,
    ) -> Result<Vec<Digest>, StorageError> {
        let exists_futures = digests
            .into_iter()
            .chunks(FIND_MISSING_BLOBS_BATCH_SIZE)
            .into_iter()
            .map(|digest_chunk_iter| {
                let digests = digest_chunk_iter.into_iter().collect::<Vec<_>>();
                let instance = instance.clone();
                async move {
                    let mut pipeline = redis::pipe();
                    for digest in &digests {
                        let key = Self::key_for_digest(&self.prefix, &instance, *digest);
                        pipeline.cmd("EXISTS").arg(key);
                    }

                    let mut conn = self.conn.get_redis_connection(false).await?;
                    let fut = redis_pipeline::<_, Vec<redis::Value>>(
                        &mut conn,
                        "EXISTS",
                        DRIVER_LABEL,
                        &pipeline,
                    );

                    let exists_results = fut.await?;
                    let exists_results: Vec<bool> =
                        <bool as FromRedisValue>::from_redis_values(exists_results.as_slice())?;
                    let missing_digests: Vec<Digest> = digests
                        .into_iter()
                        .zip(exists_results)
                        .filter_map(|(digest, exists)| if exists { None } else { Some(digest) })
                        .collect::<Vec<_>>();
                    Ok::<_, StorageError>(missing_digests)
                }
            })
            .collect::<Vec<_>>();

        let missing_digests = future::try_join_all(exists_futures)
            .await?
            .into_iter()
            .flatten()
            .collect::<Vec<_>>();

        Ok(missing_digests)
    }

    async fn read_blob(
        &self,
        instance: Instance,
        digest: Digest,
        _state: DriverState,
    ) -> Result<Option<Bytes>, StorageError> {
        let key = Self::key_for_digest(&self.prefix, &instance, digest);

        let mut conn = self.conn.get_redis_connection(false).await?;
        let data_opt: Option<Vec<u8>> = redis_query(
            &mut conn,
            "GET",
            DRIVER_LABEL,
            redis::cmd("GET").arg(key.clone()),
        )
        .await?;

        match data_opt {
            Some(data) => Ok(Some(Bytes::from(data))),
            None => Ok(None),
        }
    }

    async fn write_blob(
        &self,
        instance: Instance,
        digest: Digest,
        content: Bytes,
        _state: DriverState,
    ) -> Result<(), StorageError> {
        let mut conn = self.conn.get_redis_connection(true).await?;
        let key = Self::key_for_digest(&self.prefix, &instance, digest);
        redis_query::<_, ()>(
            &mut conn,
            "SET",
            DRIVER_LABEL,
            redis::cmd("SET").arg(&key).arg(&content[..]),
        )
        .await?;

        Ok(())
    }
}

impl<C> RedisDirectStorage<C>
where
    C: ConnectionGetter + Clone + Send + Sync + 'static,
{
    pub async fn new(conn: C, prefix: Option<String>) -> Result<Self, StorageError> {
        Ok(RedisDirectStorage {
            conn,
            prefix: prefix.unwrap_or_else(|| "".to_owned()),
        })
    }

    fn key_for_digest(prefix: &str, instance: &Instance, digest: Digest) -> String {
        format!(
            "{}{}-{}-{}",
            prefix,
            &instance.name,
            digest.hex(),
            digest.size_bytes
        )
    }
}

#[cfg(test)]
mod tests {
    use bytes::Bytes;
    use rand::{Rng, RngCore};
    use redis::{Cmd, Value as RedisValue};

    use crate::driver::{DriverState, Instance, RedisDirectStorage, SmallBlobStorage};
    use crate::testutil::TestData;
    use crate::Digest;

    use super::super::testutil::{MockCommand, MockRedisConnection};

    fn exists_cmd(key: impl AsRef<str>) -> Cmd {
        let mut cmd = redis::cmd("EXISTS");
        cmd.arg(key.as_ref());
        cmd
    }

    fn get_cmd(key: impl AsRef<str>) -> Cmd {
        let mut cmd = redis::cmd("GET");
        cmd.arg(key.as_ref());
        cmd
    }

    fn set_cmd(key: impl AsRef<str>, data: Bytes) -> Cmd {
        let mut cmd = redis::cmd("SET");
        cmd.arg(key.as_ref());
        cmd.arg(data.to_vec());
        cmd
    }

    #[tokio::test]
    async fn find_missing_blobs() {
        let content1 = TestData::from_static(b"foobar");
        let content2 = TestData::from_static(b"xyzzy");

        let conn = MockRedisConnection::new(vec![MockCommand::with_values(
            redis::pipe()
                .add_command(exists_cmd(format!(
                    "foo-main-{}-{}",
                    content1.digest.hex(),
                    content1.digest.size_bytes
                )))
                .add_command(exists_cmd(format!(
                    "foo-main-{}-{}",
                    content2.digest.hex(),
                    content2.digest.size_bytes
                ))),
            Ok(vec!["1", "0"]),
        )]);

        let storage = RedisDirectStorage::new(conn, Some("foo-".to_owned()))
            .await
            .unwrap();
        let instance = Instance::from("main");

        let missing_digests = storage
            .find_missing_blobs(
                instance,
                vec![content1.digest, content2.digest],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert_eq!(missing_digests, vec![content2.digest])
    }

    #[tokio::test]
    async fn find_missing_blobs_multiple_batches() {
        fn random_digest() -> Digest {
            let mut hash_bytes = vec![0; 32];
            rand::thread_rng().fill_bytes(&mut hash_bytes);
            Digest::from_slice(&hash_bytes, rand::thread_rng().gen()).unwrap()
        }

        let mut pipeline1 = redis::pipe();
        let mut digests1 = Vec::new();
        let mut results1 = Vec::new();
        for _ in 0..super::FIND_MISSING_BLOBS_BATCH_SIZE {
            let digest = random_digest();
            digests1.push(digest);
            results1.push("0");
            pipeline1.add_command(exists_cmd(format!(
                "foo-main-{}-{}",
                digest.hex(),
                digest.size_bytes
            )));
        }

        let mut pipeline2 = redis::pipe();
        let digest = random_digest();
        let digests2 = vec![digest];
        let results2 = vec!["0"];
        pipeline2.add_command(exists_cmd(format!(
            "foo-main-{}-{}",
            digest.hex(),
            digest.size_bytes
        )));

        let conn = MockRedisConnection::new(vec![
            MockCommand::with_values(pipeline1, Ok(results1)),
            MockCommand::with_values(pipeline2, Ok(results2)),
        ]);

        let storage = RedisDirectStorage::new(conn, Some("foo-".to_owned()))
            .await
            .unwrap();
        let instance = Instance::from("main");

        let all_digests = {
            let mut xs = Vec::new();
            xs.extend_from_slice(&digests1);
            xs.extend_from_slice(&digests2);
            xs
        };
        let missing_digests = storage
            .find_missing_blobs(instance, all_digests, DriverState::default())
            .await
            .unwrap();
        assert_eq!(
            missing_digests.len(),
            super::FIND_MISSING_BLOBS_BATCH_SIZE + 1
        );
    }

    #[tokio::test]
    async fn read_present_blob() {
        let content = TestData::from_static(b"foobar");

        let conn = MockRedisConnection::new(vec![MockCommand::new(
            get_cmd(format!(
                "foo-main-{}-{}",
                content.digest.hex(),
                content.digest.size_bytes
            )),
            Ok(content.bytes.clone()),
        )]);

        let storage = RedisDirectStorage::new(conn, Some("foo-".to_owned()))
            .await
            .unwrap();
        let instance = Instance::from("main");

        let actual_content_opt = storage
            .read_blob(instance, content.digest, DriverState::default())
            .await
            .unwrap();
        assert_eq!(actual_content_opt, Some(content.bytes));
    }

    #[tokio::test]
    async fn read_missing_blob() {
        let content = TestData::from_static(b"foobar");

        let conn = MockRedisConnection::new(vec![MockCommand::new(
            get_cmd(format!(
                "foo-main-{}-{}",
                content.digest.hex(),
                content.digest.size_bytes
            )),
            Ok(RedisValue::Nil),
        )]);

        let storage = RedisDirectStorage::new(conn, Some("foo-".to_owned()))
            .await
            .unwrap();
        let instance = Instance::from("main");

        let content_opt = storage
            .read_blob(instance, content.digest, DriverState::default())
            .await
            .unwrap();
        assert!(content_opt.is_none());
    }

    #[tokio::test]
    async fn write_blob() {
        let content = TestData::from_static(b"foobar");

        let conn = MockRedisConnection::new(vec![MockCommand::new(
            set_cmd(
                format!(
                    "foo-main-{}-{}",
                    content.digest.hex(),
                    content.digest.size_bytes
                ),
                content.bytes.clone(),
            ),
            Ok(""),
        )]);

        let storage = RedisDirectStorage::new(conn, Some("foo-".to_owned()))
            .await
            .unwrap();
        let instance = Instance::from("main");

        storage
            .write_blob(
                instance,
                content.digest,
                content.bytes,
                DriverState::default(),
            )
            .await
            .unwrap();
    }
}
