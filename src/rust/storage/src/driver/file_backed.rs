// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::io::{ErrorKind, SeekFrom};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;

use async_trait::async_trait;
use bytes::{Bytes, BytesMut};
use digest::Digest;
use tokio::fs::File;
use tokio::io::{AsyncReadExt, AsyncSeekExt, AsyncWriteExt};

use super::Instance;
use crate::driver::{
    BoxReadStream, DriverState, StorageError, StreamingWriteError, WriteAttemptOps,
};

/// Represents an attempt to write content to the BlobStorage. Content is written to a temporary
/// file which is then renamed to the final name upon `commit`.
#[derive(Debug)]
pub struct WriteAttempt {
    file: File,
    digest: Digest,
    tmp_path: PathBuf,
    final_path: PathBuf,
}

#[async_trait]
impl WriteAttemptOps for WriteAttempt {
    async fn write(&mut self, batch: Bytes) -> Result<(), StreamingWriteError> {
        // TODO: Consider periodically checking whether another writer has finished writing the
        // file, and exiting with `StreamingWriteError::AlreadyExists` if so.
        self.file
            .write_all(&batch)
            .await
            .map_err(|err| format!("error while writing digest {:?}: {}", self.digest, err))?;
        Ok(())
    }

    async fn commit(mut self: Box<Self>) -> Result<(), StreamingWriteError> {
        // Close the temp file.
        self.file
            .shutdown()
            .await
            .map_err(|err| format!("error while writing digest {:?}: {}", self.digest, err))?;

        // Rename the temporary file to the final path. This will make the digest visible to
        // readers. It is okay to overwrite the final path. For CAS, all such content should have
        // the same content. For AC, it means that a different ActionResult will take
        // precedence.
        let rename_result = tokio::fs::rename(&self.tmp_path, &self.final_path).await;
        match rename_result {
            Ok(_) => (),
            Err(err) => match err.kind() {
                // Ignore errors where the final path already exists. This means that we raced
                // against another writer which is fine given the file should be complete in and
                // of itself.
                ErrorKind::AlreadyExists => (),

                // Otherwise return an error.
                _ => {
                    return Err(StorageError::Internal(format!(
                        "error while writing digest {:?}: {}",
                        self.digest, err
                    ))
                    .into())
                }
            },
        }

        Ok(())
    }
}

impl Drop for WriteAttempt {
    fn drop(&mut self) {
        let path = self.tmp_path.clone();
        let f = tokio::spawn(tokio::fs::remove_file(path));
        std::mem::drop(f);
    }
}

struct Inner {
    /// Path to where blobs are stored.
    instances_path: PathBuf,

    /// Path to temporary directory where writes are stored.
    tmp_blobs_path: PathBuf,

    /// Sequence number added to temporary filenames for writes.
    blob_sequence: AtomicUsize,
}

impl Inner {
    /// Compute the path in the filesystem where the content for `digest` is or will be stored.
    /// The path uses a three-level directory structure based on a prefix of the digest in order
    /// to reduce the potential number of files per directory (for filesystems that have issues
    /// with large numbers of files in a directory).
    fn path_for_digest(&self, digest: Digest, instance: &Instance) -> PathBuf {
        let hex_hash = digest.hex();
        let mut blobs_path = self.instances_path.clone();
        blobs_path.push(&instance.name);
        blobs_path.push("blobs");
        blobs_path.push(&hex_hash[0..2]);
        blobs_path.push(&hex_hash[2..4]);
        blobs_path.push(&hex_hash[4..6]);
        blobs_path.push(format!("{}-{}.bin", hex_hash, digest.size_bytes));
        blobs_path
    }

    /// Checks whether a blob is missing. If so, returns the Digest (which helps to make
    /// `find_missing_blobs` easier to implement). If not, returns None.
    async fn blob_exists(&self, digest: Digest, instance: &Instance) -> bool {
        let path = self.path_for_digest(digest, instance);
        // Note: We treat all errors as a missing digest, not just "file not found."
        tokio::fs::metadata(path).await.is_ok()
    }

    /// Checks whether a blob is missing. If so, returns the Digest (which helps to make
    /// `find_missing_blobs` easier to implement). If not, returns None.
    async fn check_blob_missing(&self, digest: Digest, instance: &Instance) -> Option<Digest> {
        if self.blob_exists(digest, instance).await {
            None
        } else {
            Some(digest)
        }
    }
}

/// A `BlobStorage` implementation that stores blob content in files in the filesystem. The files
/// are stored in a three-level directory structure under the base path. Assuming a digest is of
/// the form XXYYZZ....., the path is: {base_path}/blobs/XX/YY/ZZ/{XXYYZZdigest}-{size}.bin
pub struct FileBackedStorage {
    inner: Arc<Inner>,
}

#[async_trait]
impl super::BlobStorage for FileBackedStorage {
    async fn find_missing_blobs(
        &self,
        instance: Instance,
        digests: Vec<Digest>,
        _state: DriverState,
    ) -> Result<Vec<Digest>, StorageError> {
        let mut missing_digests_futures = Vec::new();
        for digest in digests.into_iter() {
            if digest == Digest::EMPTY {
                continue;
            }
            missing_digests_futures.push(self.inner.check_blob_missing(digest, &instance));
        }

        let missing_digests = futures::future::join_all(missing_digests_futures)
            .await
            .into_iter()
            .flatten()
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
        _state: DriverState,
    ) -> Result<Option<BoxReadStream>, StorageError> {
        let blob_path = self.inner.path_for_digest(digest, &instance);

        let mut blob_file = match tokio::fs::File::open(blob_path).await {
            Ok(f) => f,
            Err(err) if err.kind() == std::io::ErrorKind::NotFound => return Ok(None),
            Err(err) => {
                return Err(format!("error while accessing digest {digest:?}: {err}").into())
            }
        };

        let blob_metadata = blob_file
            .metadata()
            .await
            .map_err(|err| format!("error while accessing digest {digest:?}: {err}"))?;

        let max_read_limit = if let Some(offset) = read_offset {
            blob_file
                .seek(SeekFrom::Start(offset as u64))
                .await
                .map_err(|err| format!("error while seeking in digest {digest:?}: {err}"))?;
            blob_metadata.len() as usize - offset
        } else {
            blob_metadata.len() as usize
        };

        let mut amount_to_read = match read_limit {
            Some(limit) => limit.min(max_read_limit),
            None => max_read_limit,
        };

        let stream = async_stream::stream! {
          while amount_to_read > 0 {
            let chunk_amount_read = max_batch_size.min(amount_to_read);
            let mut buffer = BytesMut::zeroed(chunk_amount_read);
            blob_file.read_exact(&mut buffer).await.map_err(|e| {
              StorageError::Unavailable(e.to_string())
            })?;
            yield Ok(buffer.freeze());
            amount_to_read -= chunk_amount_read;
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
        metrics::counter!("toolchain_storage_blobs_written_total", 1, "driver" => "file");

        if self.inner.blob_exists(digest, &instance).await {
            return Err(StreamingWriteError::AlreadyExists);
        }

        let blob_path = self.inner.path_for_digest(digest, &instance);

        let blob_directory_path = blob_path.parent().map(|p| p.to_path_buf()).ok_or_else(|| {
            StorageError::Internal("No parent directory for blob path.".to_string())
        })?;

        tokio::fs::create_dir_all(&blob_directory_path)
            .await
            .map_err(|err| format!("failed to create directory: {blob_directory_path:?}: {err}"))?;

        let sequence = self.inner.blob_sequence.fetch_add(1, Ordering::SeqCst);
        let blob_tmp_path = self.inner.tmp_blobs_path.with_file_name(format!(
            "{}-{}.seq{}",
            digest.hex(),
            digest.size_bytes,
            sequence,
        ));

        let blob_file = tokio::fs::File::create(&blob_tmp_path)
            .await
            .map_err(|err| format!("failed to create file: {blob_path:?}: {err}"))?;

        Ok(Box::new(WriteAttempt {
            file: blob_file,
            digest,
            tmp_path: blob_tmp_path,
            final_path: blob_path,
        }))
    }
}

impl FileBackedStorage {
    pub async fn new(
        base_path: impl AsRef<Path>,
        container_id: &str,
    ) -> Result<Self, StorageError> {
        let base_path = base_path.as_ref().join("v1").to_owned();

        let instances_path = base_path.join("instances");
        tokio::fs::create_dir_all(&instances_path)
            .await
            .map_err(|err| format!("failed to make directory: {instances_path:?}: {err}"))?;

        let tmp_blobs_path = base_path.join("tmp").join(container_id);
        tokio::fs::create_dir_all(&tmp_blobs_path)
            .await
            .map_err(|err| format!("failed to make directory: {tmp_blobs_path:?}: {err}"))?;

        Ok(FileBackedStorage {
            inner: Arc::new(Inner {
                instances_path,
                tmp_blobs_path,
                blob_sequence: AtomicUsize::new(0),
            }),
        })
    }
}

#[cfg(test)]
mod tests {
    use std::time::Duration;

    use bytes::Bytes;
    use tokio::time;

    use super::FileBackedStorage;
    use crate::bytes::consolidate_stream;
    use crate::driver::{BlobStorage, DriverState, Instance};
    use crate::testutil::TestData;

    #[tokio::test]
    async fn test_basic_read_write() {
        let base_path = tempfile::tempdir().unwrap();

        let mut storage = FileBackedStorage::new(base_path.path(), "test")
            .await
            .unwrap();
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
            .write(content.bytes.slice((content.bytes.len() / 2)..))
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
        assert_eq!(actual_content, content.bytes);
    }

    #[tokio::test]
    async fn test_offset_and_limit() {
        let base_path = tempfile::tempdir().unwrap();

        let mut storage = FileBackedStorage::new(base_path.path(), "test")
            .await
            .unwrap();
        let instance = Instance::from("main");
        storage.ensure_instance(&instance, DriverState::default());

        let content = TestData::from_static(b"foobar");

        let mut attempt = storage
            .begin_write_blob(instance.clone(), content.digest, DriverState::default())
            .await
            .unwrap();
        attempt.write(content.bytes).await.unwrap();
        attempt.commit().await.unwrap();

        let stream = storage
            .read_blob(
                instance.clone(),
                content.digest,
                1,
                Some(3),
                Some(6),
                DriverState::default(),
            )
            .await
            .unwrap()
            .unwrap();
        let actual_content = consolidate_stream(stream).await.unwrap();
        assert_eq!(actual_content, Bytes::from_static(b"bar"));
    }

    #[tokio::test]
    async fn test_multiple_writers() {
        let base_path = tempfile::tempdir().unwrap();

        let mut storage = FileBackedStorage::new(base_path.path(), "test")
            .await
            .unwrap();
        let instance = Instance::from("main");
        storage.ensure_instance(&instance, DriverState::default());

        let content = TestData::from_static(b"foobar");

        let mut attempt1 = storage
            .begin_write_blob(instance.clone(), content.digest, DriverState::default())
            .await
            .unwrap();
        attempt1.write(content.bytes.clone()).await.unwrap();

        let mut attempt2 = storage
            .begin_write_blob(instance.clone(), content.digest, DriverState::default())
            .await
            .unwrap();
        attempt2.write(content.bytes).await.unwrap();

        attempt1.commit().await.expect("attempt1 succeeds");
        attempt2.commit().await.expect("attempt2 succeeds");

        // Wait for tmp file deletes to process. Tokio doesn't currently have a way to
        // wait for detached async tasks.
        time::sleep(Duration::from_secs(1)).await;

        // There should only be one file under the blobs directory.
        let entries = walkdir::WalkDir::new(&base_path)
            .into_iter()
            .filter_map(|e| e.ok())
            .filter(|e| e.file_type().is_file())
            .collect::<Vec<_>>();
        println!("{entries:?}");
        assert_eq!(entries.len(), 1, "There must only be one file.");
    }
}
