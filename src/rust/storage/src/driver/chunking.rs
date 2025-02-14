// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use async_trait::async_trait;
use bytes::{Buf, Bytes, BytesMut};
use futures::StreamExt;

use crate::driver::{
    BlobStorage, BoxReadStream, DriverState, Instance, StorageError, StreamingWriteError,
    WriteAttemptOps,
};
use crate::Digest;

/// Adds chunking semantics to another storage driver.
///
/// Wraps an underlying storage driver to add batching of data in preferred chunk sizes to
/// reads and writes. This relieves the underlying storage driver from having to implement
/// that functionality.
pub struct ChunkingStorage<BS> {
    underlying: BS,
    write_chunk_size: usize,
}

struct WriteAttempt {
    underlying: Box<dyn WriteAttemptOps + Send + Sync>,
    buffer: BytesMut,
    chunk_size: usize,
}

#[async_trait]
impl<BS> BlobStorage for ChunkingStorage<BS>
where
    BS: BlobStorage + Send + Sync + 'static,
{
    async fn find_missing_blobs(
        &self,
        instance: Instance,
        digests: Vec<Digest>,
        state: DriverState,
    ) -> Result<Vec<Digest>, StorageError> {
        metrics::counter!("toolchain_storage_find_missing_blobs_total", digests.len() as u64, "driver" => "chunking");
        self.underlying
            .find_missing_blobs(instance, digests, state)
            .await
    }

    async fn read_blob(
        &self,
        instance: Instance,
        digest: Digest,
        chunk_size: usize,
        read_offset: Option<usize>,
        read_limit: Option<usize>,
        state: DriverState,
    ) -> Result<Option<BoxReadStream>, StorageError> {
        let stream_opt = self
            .underlying
            .read_blob(instance, digest, chunk_size, read_offset, read_limit, state)
            .await?;

        let mut stream = match stream_opt {
            Some(stream) => stream,
            None => return Ok(None),
        };

        let stream = async_stream::try_stream! {
            let mut buffer = BytesMut::with_capacity(chunk_size);

            while let Some(chunk_result) = stream.next().await {
                let mut chunk = chunk_result?;

                // While data remains in this chunk, attempt to batch it up and send.
                while chunk.has_remaining() {
                    debug_assert!(buffer.len() < chunk_size);
                    let bytes_remaining_to_fill_chunk = chunk_size - buffer.len();
                    debug_assert!(bytes_remaining_to_fill_chunk > 0);

                    let bytes_to_read = bytes_remaining_to_fill_chunk.min(chunk.len());
                    buffer.extend_from_slice(&chunk[0..bytes_to_read]);
                    chunk.advance(bytes_to_read);

                    // Emit the buffer if it is at the preferred size.
                    if buffer.len() >= chunk_size {
                        let item = std::mem::replace(&mut buffer, BytesMut::with_capacity(chunk_size));
                        let item = item.freeze();
                        metrics::counter!("toolchain_storage_bytes_read_total", item.len() as u64, "driver" => "chunking");
                        yield item;
                    }
                }
            }

            // Emit any remaining data.
            if !buffer.is_empty() {
                let item = std::mem::replace(&mut buffer, BytesMut::new());
                yield item.freeze();
            }
        };

        let stream = Box::pin(stream) as BoxReadStream;

        Ok(Some(stream))
    }

    async fn begin_write_blob(
        &self,
        instance: Instance,
        digest: Digest,
        state: DriverState,
    ) -> Result<Box<dyn WriteAttemptOps + Send + Sync>, StreamingWriteError> {
        metrics::counter!("toolchain_storage_blobs_written_total", 1, "driver" => "chunking");
        let attempt = self
            .underlying
            .begin_write_blob(instance, digest, state)
            .await?;
        let wrapped_attempt = WriteAttempt {
            underlying: attempt,
            buffer: BytesMut::with_capacity(self.write_chunk_size),
            chunk_size: self.write_chunk_size,
        };
        Ok(Box::new(wrapped_attempt))
    }
}

impl WriteAttempt {
    /// Stores the current buffer into the underlying storage driver and sets up a fresh
    /// buffer for further writes.
    async fn store_buffer(&mut self, last: bool) -> Result<(), StreamingWriteError> {
        let chunk_size = if last { 0 } else { self.chunk_size };
        let buffer = std::mem::replace(&mut self.buffer, BytesMut::with_capacity(chunk_size));
        let buffer = buffer.freeze();
        self.underlying.write(buffer).await?;
        Ok(())
    }
}

#[async_trait]
impl WriteAttemptOps for WriteAttempt {
    async fn write(&mut self, mut data: Bytes) -> Result<(), StreamingWriteError> {
        metrics::counter!("toolchain_storage_bytes_written_total", data.len() as u64, "driver" => "chunking");

        // Write the data into the temporary buffer used to create the chunk.
        while data.has_remaining() {
            // Attempt to fill the current chunk from the buffer to the preferred size.
            debug_assert!(self.buffer.len() < self.chunk_size);
            let bytes_remaining_to_fill_chunk = self.chunk_size - self.buffer.len();
            debug_assert!(bytes_remaining_to_fill_chunk > 0);

            // Copy the next set of bytes into the chunk.
            let bytes_to_read = bytes_remaining_to_fill_chunk.min(data.len());
            self.buffer.extend_from_slice(&data[0..bytes_to_read]);
            data.advance(bytes_to_read);

            // If the buffer is at the preferred size, send it the underlying driver.
            if self.buffer.len() >= self.chunk_size {
                self.store_buffer(false).await?;
            }
        }

        Ok(())
    }

    async fn commit(mut self: Box<Self>) -> Result<(), StreamingWriteError> {
        if !self.buffer.is_empty() {
            self.store_buffer(true).await?;
        }
        self.underlying.commit().await?;
        Ok(())
    }
}

impl<BS> ChunkingStorage<BS>
where
    BS: BlobStorage + Send + Sync + 'static,
{
    #[allow(dead_code)]
    pub fn new(underlying: BS, write_chunk_size: usize) -> Self {
        ChunkingStorage {
            underlying,
            write_chunk_size,
        }
    }

    #[allow(dead_code)]
    pub fn into_inner(self) -> BS {
        self.underlying
    }

    #[allow(dead_code)]
    pub fn get_inner(&self) -> &BS {
        &self.underlying
    }
}

#[cfg(test)]
mod tests {
    use std::collections::VecDeque;
    use std::fmt::Write;
    use std::sync::Arc;

    use async_trait::async_trait;
    use bytes::{Bytes, BytesMut};
    use futures::{future, FutureExt, Stream, TryStreamExt};
    use parking_lot::Mutex;

    use crate::driver::chunking::ChunkingStorage;
    use crate::driver::{
        BlobStorage, BoxReadStream, DriverState, Instance, StorageError, StreamingWriteError,
        WriteAttemptOps,
    };
    use crate::Digest;

    struct TestStorage {
        reads: Arc<Mutex<VecDeque<Vec<usize>>>>,
        writes: Arc<Mutex<VecDeque<Vec<usize>>>>,
    }

    struct TestWriteAttempt {
        chunk_sizes: Vec<usize>,
        writes: Arc<Mutex<VecDeque<Vec<usize>>>>,
    }

    #[async_trait]
    impl BlobStorage for TestStorage {
        async fn find_missing_blobs(
            &self,
            _instance: Instance,
            _digests: Vec<Digest>,
            _state: DriverState,
        ) -> Result<Vec<Digest>, StorageError> {
            Ok(Vec::new())
        }

        async fn read_blob(
            &self,
            _instance: Instance,
            digest: Digest,
            _max_batch_size: usize,
            _read_offset: Option<usize>,
            _read_limit: Option<usize>,
            _state: DriverState,
        ) -> Result<Option<BoxReadStream>, StorageError> {
            let size = digest.size_bytes;
            let (content, _) = make_content(size);
            let read_sizes = match self.reads.lock().pop_front() {
                Some(rs) => rs,
                None => return Ok(None),
            };

            let stream = futures::stream::unfold(Some(0usize), move |state| {
                let chunk_num = match state {
                    Some(n) => n,
                    None => return future::ready(None).boxed(),
                };

                if chunk_num >= read_sizes.len() {
                    return future::ready(None).boxed();
                }

                let read_size = read_sizes[chunk_num];
                let item = content.slice(0..read_size);
                future::ready(Some((Ok(item), Some(chunk_num + 1)))).boxed()
            });

            let stream = Box::pin(stream) as BoxReadStream;

            Ok(Some(stream))
        }

        async fn begin_write_blob(
            &self,
            _instance: Instance,
            _digest: Digest,
            _state: DriverState,
        ) -> Result<Box<dyn WriteAttemptOps + Send + Sync>, StreamingWriteError> {
            Ok(Box::new(TestWriteAttempt {
                writes: self.writes.clone(),
                chunk_sizes: Vec::new(),
            }))
        }
    }

    #[async_trait]
    impl WriteAttemptOps for TestWriteAttempt {
        async fn write(&mut self, chunk: Bytes) -> Result<(), StreamingWriteError> {
            self.chunk_sizes.push(chunk.len());
            Ok(())
        }

        async fn commit(self: Box<Self>) -> Result<(), StreamingWriteError> {
            self.writes.lock().push_back(self.chunk_sizes);
            Ok(())
        }
    }

    fn make_content(n: usize) -> (Bytes, Digest) {
        let mut buffer = BytesMut::with_capacity(n);
        for _ in 0..n {
            buffer.write_char('x').unwrap();
        }
        let buffer = buffer.freeze();
        let digest = Digest::of_bytes(&buffer).unwrap();
        (buffer, digest)
    }

    fn fake_digest(n: usize) -> Digest {
        Digest {
            hash: Digest::EMPTY.hash,
            size_bytes: n,
        }
    }

    async fn collect_lengths(
        stream: impl Stream<Item = Result<Bytes, StorageError>> + Unpin,
    ) -> Result<Vec<usize>, StorageError> {
        stream.map_ok(|buf| buf.len()).try_collect::<Vec<_>>().await
    }

    #[tokio::test]
    async fn writes_chunk_as_expected() {
        let test_storage = TestStorage {
            writes: Arc::new(Mutex::new(VecDeque::new())),
            reads: Arc::new(Mutex::new(VecDeque::new())),
        };
        let mut storage = ChunkingStorage::new(test_storage, 5);

        let instance = Instance::from("main");
        storage.ensure_instance(&instance, DriverState::default());

        // Test: Write the entire blob at once (on chunk boundary).
        let (content, digest) = make_content(10);
        let mut attempt = storage
            .begin_write_blob(instance.clone(), digest, DriverState::default())
            .await
            .unwrap();
        attempt.write(content).await.unwrap();
        attempt.commit().await.unwrap();
        {
            let actual_writes = storage.get_inner().writes.lock().pop_front().unwrap();
            assert_eq!(actual_writes, vec![5, 5]);
        }

        // Test: Write the entire blob at once (not on chunk boundary).
        let (content, digest) = make_content(12);
        let mut attempt = storage
            .begin_write_blob(instance.clone(), digest, DriverState::default())
            .await
            .unwrap();
        attempt.write(content).await.unwrap();
        attempt.commit().await.unwrap();
        {
            let actual_writes = storage.get_inner().writes.lock().pop_front().unwrap();
            assert_eq!(actual_writes, vec![5, 5, 2]);
        }

        // Test: Write less than chunk size each time, result is not on chunk boundary.
        let (content, digest) = make_content(12);
        let mut attempt = storage
            .begin_write_blob(instance.clone(), digest, DriverState::default())
            .await
            .unwrap();
        attempt.write(content.slice(0..4)).await.unwrap();
        attempt.write(content.slice(4..8)).await.unwrap();
        attempt.write(content.slice(8..12)).await.unwrap();
        attempt.commit().await.unwrap();
        {
            let actual_writes = storage.get_inner().writes.lock().pop_front().unwrap();
            assert_eq!(actual_writes, vec![5, 5, 2]);
        }

        // Test: Write one of the chunks larger than chunk size, result is not on chunk boundary.
        let (content, digest) = make_content(12);
        let mut attempt = storage
            .begin_write_blob(instance, digest, DriverState::default())
            .await
            .unwrap();
        attempt.write(content.slice(0..4)).await.unwrap();
        attempt.write(content.slice(4..12)).await.unwrap();
        attempt.commit().await.unwrap();
        {
            let actual_writes = storage.get_inner().writes.lock().pop_front().unwrap();
            assert_eq!(actual_writes, vec![5, 5, 2]);
        }
    }

    #[tokio::test]
    async fn reads_chunk_as_expected() {
        let test_storage = TestStorage {
            writes: Arc::new(Mutex::new(VecDeque::new())),
            reads: Arc::new(Mutex::new(VecDeque::new())),
        };
        let mut storage = ChunkingStorage::new(test_storage, 5);

        let instance = Instance::from("main");
        storage.ensure_instance(&instance, DriverState::default());

        // Test: Underlying driver returns chunks with the exact preferred chunk size.
        let digest = fake_digest(10);
        storage.underlying.reads.lock().push_back(vec![5, 5]);
        let stream = storage
            .read_blob(
                instance.clone(),
                digest,
                5,
                None,
                None,
                DriverState::default(),
            )
            .await
            .unwrap()
            .unwrap();
        let lengths = collect_lengths(stream).await.unwrap();
        assert_eq!(lengths, vec![5, 5]);

        // Test: Underlying driver returns chunks with more than the preferred chunk size.
        let digest = fake_digest(17);
        storage.underlying.reads.lock().push_back(vec![10, 7]);
        let stream = storage
            .read_blob(
                instance.clone(),
                digest,
                5,
                None,
                None,
                DriverState::default(),
            )
            .await
            .unwrap()
            .unwrap();
        let lengths = collect_lengths(stream).await.unwrap();
        assert_eq!(lengths, vec![5, 5, 5, 2]);

        // Test: Underlying driver returns chunks that are less than the preferred chunk size.
        let digest = fake_digest(12);
        storage.underlying.reads.lock().push_back(vec![4, 4, 4]);
        let stream = storage
            .read_blob(instance, digest, 5, None, None, DriverState::default())
            .await
            .unwrap()
            .unwrap();
        let lengths = collect_lengths(stream).await.unwrap();
        assert_eq!(lengths, vec![5, 5, 2]);
    }
}
