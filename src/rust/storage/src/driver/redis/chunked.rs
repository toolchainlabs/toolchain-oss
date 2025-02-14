// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use async_trait::async_trait;
use bytes::Bytes;
use futures::{future, FutureExt};
use prost::Message;

use super::common::{redis_pipeline, redis_query, ConnectionGetter};
use crate::driver::{
    BlobStorage, BoxReadStream, DriverState, Instance, StorageError, StreamingWriteError,
    WriteAttemptOps,
};
use crate::protos::toolchain::storage::redis::RedisMetadataChunk;
use crate::uuid_gen::{DefaultUuidGenerator, UuidGenerator};
use crate::Digest;

/// Label used for metrics.
const DRIVER_LABEL: &str = "redis";

/// Stores blobs in Redis using a "chunked" encoding where blobs are split into one or more
/// chunks. Supports multiple instances.
///
/// The Redis cache is used to implement several virtual data maps:
/// * Data Map
///   - Stores the actual content of a blob. Maps (UUID on upload, block number) to data for
///     the block.
///   - Name format: INSTANCE:data-UUID-BLOCK
///   - There is also a "metadata chunk" which stores the total number of chunks for the blob.
///     The BLOCK in the name is `meta` for this metadata chunk.
/// * CAS Index Maps:
///   - Maps a content hash to the UUID in the Data Map for the blob. There is one Index Map
///     per digest function per REAPI instance.
///   - Name format: INSTANCE:index-sha256-DIGEST_HASH-DIGEST_SIZE
///
/// Note: This driver must be used in conjunction with `ChunkingStorage` in order to manage
/// the size of the chunks of blobs stored in Redis.
pub struct RedisStorage<C, UG = DefaultUuidGenerator>
where
    C: ConnectionGetter + Clone + Send + Sync + 'static,
    UG: UuidGenerator + Send + Sync,
{
    conn: C,
    prefix: String,
    uuid_generator: UG,
}

struct RedisWriteAttempt<C>
where
    C: ConnectionGetter + Clone + Send + Sync + 'static,
{
    instance: Instance,
    uuid: String,
    base_key: String,
    prefix: String,
    digest: Digest,
    chunk_num: u64, // match type used in the protobuf definition of the metadata chunk
    conn: C,
}

#[async_trait]
impl<C, UG> BlobStorage for RedisStorage<C, UG>
where
    C: ConnectionGetter + Clone + Send + Sync + 'static,
    UG: UuidGenerator + Send + Sync,
{
    async fn find_missing_blobs(
        &self,
        instance: Instance,
        digests: Vec<Digest>,
        _state: DriverState,
    ) -> Result<Vec<Digest>, StorageError> {
        let exists_futures = digests
            .into_iter()
            .map(|digest| {
                Self::check_digest_does_not_exist(&instance, &self.conn, digest, &self.prefix)
            })
            .collect::<Vec<_>>();
        let exists_responses = future::try_join_all(exists_futures).await?;
        let missing_digests = exists_responses
            .iter()
            .flatten()
            .cloned()
            .collect::<Vec<_>>();
        Ok(missing_digests)
    }

    async fn read_blob(
        &self,
        instance: Instance,
        digest: Digest,
        _max_batch_size: usize,
        _read_offset: Option<usize>,
        _read_limit: Option<usize>,
        _state: DriverState,
    ) -> Result<Option<BoxReadStream>, StorageError> {
        async fn fetch_chunk<C>(conn: C, key: String) -> Result<Bytes, StorageError>
        where
            C: ConnectionGetter + Clone + Send + Sync + 'static,
        {
            let mut conn = conn.get_redis_connection(false).await?;

            let data_vec_opt: Option<Vec<u8>> = redis_query(
                &mut conn,
                "GET",
                DRIVER_LABEL,
                redis::cmd("GET").arg(key.clone()),
            )
            .await?;

            let data_vec = match data_vec_opt {
                Some(data_vec) => data_vec,
                None => return Err(StorageError::Internal(format!("Missing data block: {key}"))),
            };

            Ok(Bytes::copy_from_slice(&data_vec[..]))
        }

        // Check if all keys for the blob exist first.
        // Note: This is inefficient because we duplicate rereading the Index Map, but for now
        // this allows reusing the same code used by `find_missing_blobs`.
        if Self::check_digest_does_not_exist(&instance, &self.conn, digest, &self.prefix)
            .await?
            .is_some()
        {
            return Ok(None);
        }

        let mut conn = self.conn.get_redis_connection(false).await?;

        let index_map_key = format!(
            "{}{}:index-sha256-{}-{}",
            &self.prefix,
            &instance.name,
            digest.hex(),
            digest.size_bytes
        );

        // Query the Index Map for the UUID in the Data Map.
        // https://redis.io/commands/get
        let uuid_opt: Option<String> = redis_query(
            &mut conn,
            "GET",
            DRIVER_LABEL,
            redis::cmd("GET").arg(index_map_key),
        )
        .await?;

        let uuid = match uuid_opt {
            Some(uuid) => uuid,
            None => return Ok(None),
        };

        let data_map_key_base = format!("{}{}:data-{}", &self.prefix, &instance.name, &uuid);
        let metadata_key = format!("{}-meta", &data_map_key_base);

        // Query the Data Map for this block's metadata chunk.
        let metadata_opt: Option<Vec<u8>> = redis_query(
            &mut conn,
            "GET",
            DRIVER_LABEL,
            redis::cmd("GET").arg(&metadata_key),
        )
        .await?;

        let metadata = match metadata_opt {
            Some(data) => RedisMetadataChunk::decode(&data[..])
                .map_err(|_| StorageError::Internal("Corrupt metadata chunk".to_owned()))?,
            None => {
                // TODO: If metadata chunk is missing, then delete this entry from the Index Map.
                return Ok(None);
            }
        };

        let num_chunks = metadata.num_chunks;
        let conn_clone = self.conn.clone();
        let stream = futures::stream::unfold(Some(0u64), move |state| {
            let chunk_num = match state {
                Some(n) => n,
                None => return future::ready(None).boxed(),
            };

            if chunk_num >= num_chunks {
                return future::ready(None).boxed();
            }

            let key = format!("{}-{}", &data_map_key_base, chunk_num);
            let conn2 = conn_clone.clone();
            (async move {
                let item = fetch_chunk(conn2, key).await;
                match item {
                    Ok(chunk) => Some((Ok(chunk), Some(chunk_num + 1))),
                    Err(err) => Some((Err(err), None)),
                }
            })
            .boxed()
        });

        let stream = Box::pin(stream) as BoxReadStream;

        Ok(Some(stream))
    }

    async fn begin_write_blob(
        &self,
        instance: Instance,
        digest: Digest,
        _state: DriverState,
    ) -> Result<Box<dyn WriteAttemptOps + Send + Sync + 'static>, StreamingWriteError> {
        let uuid = self.uuid_generator.generate_uuid();
        let base_key = format!("{}{}:data-{}", &self.prefix, &instance.name, uuid);
        Ok(Box::new(RedisWriteAttempt {
            instance,
            uuid,
            base_key,
            prefix: self.prefix.clone(),
            digest,
            chunk_num: 0,
            conn: self.conn.clone(),
        }))
    }
}

#[async_trait]
impl<C> WriteAttemptOps for RedisWriteAttempt<C>
where
    C: ConnectionGetter + Clone + Send + Sync + 'static,
{
    async fn write(&mut self, data: Bytes) -> Result<(), StreamingWriteError> {
        let mut conn = self.conn.get_redis_connection(true).await?;

        // Store this chunk in Redis.
        // https://redis.io/commands/setex
        let key = format!("{}-{}", &self.base_key, self.chunk_num);
        redis_query(
            &mut conn,
            "SET",
            DRIVER_LABEL,
            redis::cmd("SET").arg(&key).arg(&data[..]),
        )
        .await?;

        self.chunk_num += 1;

        Ok(())
    }

    async fn commit(mut self: Box<Self>) -> Result<(), StreamingWriteError> {
        let mut conn = self.conn.get_redis_connection(true).await?;

        // Write the metadata chunk with the total number of chunks written.
        let metadata_key = format!("{}-meta", &self.base_key);
        let metadata = RedisMetadataChunk {
            num_chunks: self.chunk_num,
        };
        let mut metadata_value = Vec::with_capacity(metadata.encoded_len());
        metadata
            .encode(&mut metadata_value)
            .map_err(|_| StorageError::Internal("Failed to encode metadata chunk".to_owned()))?;

        redis_query(
            &mut conn,
            "SET",
            DRIVER_LABEL,
            redis::cmd("SET").arg(&metadata_key).arg(metadata_value),
        )
        .await?;

        // Update the Index Map to map this digest to this upload. This upload will
        // be visible for this Digest after this operation completes.
        let index_map_key = format!(
            "{}{}:index-sha256-{}-{}",
            &self.prefix,
            &self.instance.name,
            self.digest.hex(),
            self.digest.size_bytes
        );
        redis_query(
            &mut conn,
            "SET",
            DRIVER_LABEL,
            redis::cmd("SET").arg(&index_map_key).arg(&self.uuid),
        )
        .await?;

        Ok(())
    }
}

impl<C, UG> RedisStorage<C, UG>
where
    C: ConnectionGetter + Clone + Send + Sync + 'static,
    UG: UuidGenerator + Send + Sync,
{
    pub async fn new(
        client: C,
        prefix: Option<String>,
        uuid_generator: UG,
    ) -> Result<Self, StorageError> {
        Ok(RedisStorage {
            conn: client,
            prefix: prefix.unwrap_or_else(|| "".to_owned()),
            uuid_generator,
        })
    }

    /// Checks whether a digest exists and returns the digest if it is missing (i.e., does
    /// **not** exist). The existence check is inverted to better support the `find_missing_blobs`
    /// RPC which returns missing blobs.
    async fn check_digest_does_not_exist(
        instance: &Instance,
        connection_manager: &C,
        digest: Digest,
        prefix: &str,
    ) -> Result<Option<Digest>, StorageError>
    where
        C: ConnectionGetter + Clone + Send + Sync,
    {
        let mut conn = connection_manager.get_redis_connection(false).await?;

        // Check the Index Map for the blob.

        let index_map_key = format!(
            "{}{}:index-sha256-{}-{}",
            prefix,
            &instance.name,
            digest.hex(),
            digest.size_bytes
        );

        let uuid_opt: Option<String> = redis_query(
            &mut conn,
            "GET",
            DRIVER_LABEL,
            redis::cmd("GET").arg(index_map_key),
        )
        .await?;

        let uuid = match uuid_opt {
            Some(uuid) => uuid,
            None => return Ok(Some(digest)),
        };

        let data_map_key_base = format!("{}{}:data-{}", prefix, &instance.name, uuid);

        // Query the Data Map for this digest's metadata chunk.
        let metadata_key = format!("{}-meta", &data_map_key_base);
        let metadata_opt: Option<Vec<u8>> = redis_query(
            &mut conn,
            "GET",
            DRIVER_LABEL,
            redis::cmd("GET").arg(&metadata_key),
        )
        .await?;
        let metadata = match metadata_opt {
            Some(data) => RedisMetadataChunk::decode(&data[..])
                .map_err(|_| StorageError::Internal("Corrupt metadata chunk".to_owned()))?,
            None => {
                // TODO: If metadata chunk is missing, then delete this entry from the Index Map.
                return Ok(Some(digest));
            }
        };

        // Loop through the data blocks and ensure that they all exist.
        let mut pipeline = redis::pipe();
        for chunk_num in 0..metadata.num_chunks {
            let key = format!("{}-{}", &data_map_key_base, chunk_num);
            pipeline.cmd("EXISTS").arg(key);
        }

        let result: Vec<bool> =
            redis_pipeline(&mut conn, "EXISTS", DRIVER_LABEL, &pipeline).await?;
        if result.iter().any(|v| !*v) {
            // TODO: If data chunk is missing, then delete this entry from the Index Map.
            return Ok(Some(digest));
        }

        // If execution reaches this point, then all blocks exist.
        Ok(None)
    }
}

#[cfg(test)]
mod tests {
    use prost::Message;
    use redis::{Cmd, ToRedisArgs};

    use super::super::testutil::{MockCommand, MockRedisConnection};
    use super::RedisStorage;
    use crate::bytes::consolidate_stream;
    use crate::driver::{BlobStorage, ChunkingStorage, DriverState, Instance, WriteDigestVerifier};
    use crate::protos::toolchain::storage::redis::RedisMetadataChunk;
    use crate::testutil::TestData;
    use crate::uuid_gen::{DefaultUuidGenerator, UuidGenerator};

    struct TestUuidGenerator;

    impl UuidGenerator for TestUuidGenerator {
        fn generate_uuid(&self) -> String {
            "abc123".to_owned()
        }
    }

    fn metadata_value(num_chunks: u64) -> Vec<u8> {
        let metadata = RedisMetadataChunk { num_chunks };
        let mut buffer = Vec::with_capacity(metadata.encoded_len());
        metadata.encode(&mut buffer).unwrap();
        buffer
    }

    fn get_cmd(key: impl AsRef<str>) -> Cmd {
        let mut cmd = redis::cmd("GET");
        cmd.arg(key.as_ref());
        cmd
    }

    fn set_cmd(key: impl AsRef<str>, value: impl ToRedisArgs) -> Cmd {
        let mut cmd = redis::cmd("SET");
        cmd.arg(key.as_ref()).arg(value);
        cmd
    }

    #[tokio::test]
    async fn find_missing_blobs() {
        let content1 = TestData::from_static(b"foobar");
        let content2 = TestData::from_static(b"xyzzy-grok");

        let conn = MockRedisConnection::new(vec![
            MockCommand::new(
                get_cmd(format!(
                    "main:index-sha256-{}-{}",
                    content1.digest.hex(),
                    content1.digest.size_bytes
                )),
                Ok("abc123".to_owned()),
            ),
            MockCommand::new(get_cmd("main:data-abc123-meta"), Ok(metadata_value(1))),
            MockCommand::with_values(
                redis::pipe().cmd("EXISTS").arg("main:data-abc123-0"),
                Ok(vec!["1"]),
            ),
            MockCommand::new(
                get_cmd(format!(
                    "main:index-sha256-{}-{}",
                    content2.digest.hex(),
                    content2.digest.size_bytes
                )),
                Ok("abc123".to_owned()),
            ),
            MockCommand::new(get_cmd("main:data-abc123-meta"), Ok(metadata_value(1))),
            MockCommand::with_values(
                redis::pipe().cmd("EXISTS").arg("main:data-abc123-0"),
                Ok(vec!["0"]),
            ),
        ]);

        let mut storage = RedisStorage::new(conn, None, DefaultUuidGenerator)
            .await
            .unwrap();
        let instance = Instance::from("main");
        storage.ensure_instance(&instance, DriverState::default());

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
    async fn read_blob_success() {
        let content = TestData::from_static(b"xyzzy-grok");

        let conn = MockRedisConnection::new(vec![
            MockCommand::new(
                get_cmd(format!(
                    "main:index-sha256-{}-{}",
                    content.digest.hex(),
                    content.digest.size_bytes
                )),
                Ok("abc123".to_owned()),
            ),
            MockCommand::new(get_cmd("main:data-abc123-meta"), Ok(metadata_value(1))),
            MockCommand::with_values(
                redis::pipe().cmd("EXISTS").arg("main:data-abc123-0"),
                Ok(vec!["1"]),
            ),
            MockCommand::new(
                get_cmd(format!(
                    "main:index-sha256-{}-{}",
                    content.digest.hex(),
                    content.digest.size_bytes
                )),
                Ok("abc123".to_owned()),
            ),
            MockCommand::new(get_cmd("main:data-abc123-meta"), Ok(metadata_value(1))),
            MockCommand::new(get_cmd("main:data-abc123-0"), Ok(content.bytes.clone())),
        ]);

        let mut storage = RedisStorage::new(conn, None, DefaultUuidGenerator)
            .await
            .unwrap();
        let instance = Instance::from("main");
        storage.ensure_instance(&instance, DriverState::default());

        let stream = storage
            .read_blob(
                instance,
                content.digest,
                1024,
                None,
                None,
                DriverState::default(),
            )
            .await
            .unwrap()
            .unwrap();
        let buffer = consolidate_stream(stream).await.unwrap();
        assert_eq!(buffer, content.bytes);
    }

    #[tokio::test]
    async fn write_blob() {
        let content = TestData::from_static(b"xyzzy-grok");

        let conn = MockRedisConnection::new(vec![
            MockCommand::new(
                set_cmd("main:data-abc123-0", content.bytes.slice(0..6).as_ref()),
                Ok(""),
            ),
            MockCommand::new(
                set_cmd("main:data-abc123-1", content.bytes.slice(6..).as_ref()),
                Ok(""),
            ),
            MockCommand::new(set_cmd("main:data-abc123-meta", metadata_value(2)), Ok("")),
            MockCommand::new(
                set_cmd(
                    format!(
                        "main:index-sha256-{}-{}",
                        content.digest.hex(),
                        content.digest.size_bytes
                    ),
                    "abc123",
                ),
                Ok(""),
            ),
        ]);

        let mut storage = RedisStorage::new(conn, None, TestUuidGenerator)
            .await
            .unwrap();
        let instance = Instance::from("main");
        storage.ensure_instance(&instance, DriverState::default());

        let mut attempt = storage
            .begin_write_blob(instance, content.digest, DriverState::default())
            .await
            .unwrap();
        attempt.write(content.bytes.slice(0..6)).await.unwrap();
        attempt.write(content.bytes.slice(6..)).await.unwrap();
        attempt.commit().await.unwrap();
    }

    #[tokio::test]
    async fn prefixed_keys() {
        let content = TestData::from_static(b"xyzzy-grok");

        let conn = MockRedisConnection::new(vec![
            // find missing blob
            MockCommand::new(
                get_cmd(format!(
                    "foo-main:index-sha256-{}-{}",
                    content.digest.hex(),
                    content.digest.size_bytes
                )),
                Ok("abc123".to_owned()),
            ),
            MockCommand::new(get_cmd("foo-main:data-abc123-meta"), Ok(metadata_value(1))),
            MockCommand::with_values(
                redis::pipe().cmd("EXISTS").arg("foo-main:data-abc123-0"),
                Ok(vec!["0"]),
            ),
            // write
            MockCommand::new(
                set_cmd("foo-main:data-abc123-0", content.bytes.as_ref()),
                Ok(""),
            ),
            MockCommand::new(
                set_cmd("foo-main:data-abc123-meta", metadata_value(1)),
                Ok(""),
            ),
            MockCommand::new(
                set_cmd(
                    format!(
                        "foo-main:index-sha256-{}-{}",
                        content.digest.hex(),
                        content.digest.size_bytes
                    ),
                    "abc123",
                ),
                Ok(""),
            ),
            // read
            MockCommand::new(
                get_cmd(format!(
                    "foo-main:index-sha256-{}-{}",
                    content.digest.hex(),
                    content.digest.size_bytes
                )),
                Ok("abc123".to_owned()),
            ),
            MockCommand::new(get_cmd("foo-main:data-abc123-meta"), Ok(metadata_value(1))),
            MockCommand::with_values(
                redis::pipe().cmd("EXISTS").arg("foo-main:data-abc123-0"),
                Ok(vec!["1"]),
            ),
            MockCommand::new(
                get_cmd(format!(
                    "foo-main:index-sha256-{}-{}",
                    content.digest.hex(),
                    content.digest.size_bytes
                )),
                Ok("abc123".to_owned()),
            ),
            MockCommand::new(get_cmd("foo-main:data-abc123-meta"), Ok(metadata_value(1))),
            MockCommand::new(get_cmd("foo-main:data-abc123-0"), Ok(content.bytes.clone())),
        ]);

        let mut storage = RedisStorage::new(conn, Some("foo-".into()), TestUuidGenerator)
            .await
            .unwrap();
        let instance = Instance::from("main");
        storage.ensure_instance(&instance, DriverState::default());

        let missing_digests = storage
            .find_missing_blobs(
                instance.clone(),
                vec![content.digest],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert_eq!(missing_digests, vec![content.digest]);

        let mut attempt = storage
            .begin_write_blob(instance.clone(), content.digest, DriverState::default())
            .await
            .unwrap();
        attempt.write(content.bytes.clone()).await.unwrap();
        attempt.commit().await.unwrap();

        let stream = storage
            .read_blob(
                instance,
                content.digest,
                1024,
                None,
                None,
                DriverState::default(),
            )
            .await
            .unwrap()
            .unwrap();
        let buffer = consolidate_stream(stream).await.unwrap();
        assert_eq!(buffer, content.bytes);
    }

    #[tokio::test]
    async fn missing_keys_are_treated_as_missing_digests() {
        let content = TestData::from_static(b"foobar");

        let conn = MockRedisConnection::new(vec![
            // second data chunk is missing
            MockCommand::new(
                get_cmd(format!(
                    "main:index-sha256-{}-{}",
                    content.digest.hex(),
                    content.digest.size_bytes
                )),
                Ok("abc123".to_owned()),
            ),
            MockCommand::new(get_cmd("main:data-abc123-meta"), Ok(metadata_value(2))),
            MockCommand::with_values(
                redis::pipe()
                    .cmd("EXISTS")
                    .arg("main:data-abc123-0")
                    .cmd("EXISTS")
                    .arg("main:data-abc123-1"),
                Ok(vec!["1", "0"]),
            ),
            MockCommand::new(
                get_cmd(format!(
                    "main:index-sha256-{}-{}",
                    content.digest.hex(),
                    content.digest.size_bytes
                )),
                Ok("abc123".to_owned()),
            ),
            MockCommand::new(get_cmd("main:data-abc123-meta"), Ok(metadata_value(2))),
            MockCommand::with_values(
                redis::pipe()
                    .cmd("EXISTS")
                    .arg("main:data-abc123-0")
                    .cmd("EXISTS")
                    .arg("main:data-abc123-1"),
                Ok(vec!["0", "1"]),
            ),
            // verify read also treats the digest as missing
            MockCommand::new(
                get_cmd(format!(
                    "main:index-sha256-{}-{}",
                    content.digest.hex(),
                    content.digest.size_bytes
                )),
                Ok("abc123".to_owned()),
            ),
            MockCommand::new(get_cmd("main:data-abc123-meta"), Ok(metadata_value(2))),
            MockCommand::with_values(
                redis::pipe()
                    .cmd("EXISTS")
                    .arg("main:data-abc123-0")
                    .cmd("EXISTS")
                    .arg("main:data-abc123-1"),
                Ok(vec!["0", "1"]),
            ),
        ]);

        let mut storage = RedisStorage::new(conn, None, DefaultUuidGenerator)
            .await
            .unwrap();
        let instance = Instance::from("main");
        storage.ensure_instance(&instance, DriverState::default());

        // second data chunk is missing
        let missing_digests = storage
            .find_missing_blobs(
                instance.clone(),
                vec![content.digest],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert_eq!(missing_digests, vec![content.digest]);

        // first data chunk is missing which short circuits the scan
        let missing_digests = storage
            .find_missing_blobs(
                instance.clone(),
                vec![content.digest],
                DriverState::default(),
            )
            .await
            .unwrap();
        assert_eq!(missing_digests, vec![content.digest]);

        // verify read also treats the digest as missing
        let read_result = storage
            .read_blob(
                instance,
                content.digest,
                1024,
                None,
                None,
                DriverState::default(),
            )
            .await
            .unwrap();
        assert!(read_result.is_none());
    }

    #[tokio::test]
    async fn redis_chunking_functional_test() {
        let content = TestData::from_static(b"foobar");

        let conn = MockRedisConnection::new(vec![
            MockCommand::new(
                set_cmd("main:data-abc123-0", content.bytes.as_ref()),
                Ok(""),
            ),
            MockCommand::new(set_cmd("main:data-abc123-meta", metadata_value(1)), Ok("")),
            MockCommand::new(
                set_cmd(
                    format!(
                        "main:index-sha256-{}-{}",
                        content.digest.hex(),
                        content.digest.size_bytes
                    ),
                    "abc123",
                ),
                Ok(""),
            ),
        ]);

        let mut storage = RedisStorage::new(conn, None, TestUuidGenerator)
            .await
            .unwrap();
        let instance = Instance::from("main");
        storage.ensure_instance(&instance, DriverState::default());

        let storage = ChunkingStorage::new(storage, 512 * 1024);
        let storage = WriteDigestVerifier::new(storage);

        let mut attempt = storage
            .begin_write_blob(instance, content.digest, DriverState::default())
            .await
            .unwrap();
        attempt.write(content.bytes).await.unwrap();
        attempt.commit().await.unwrap();
    }
}
