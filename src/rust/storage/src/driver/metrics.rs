// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::pin::Pin;
use std::task::{Context, Poll};
use std::time::{Duration, Instant};

use async_trait::async_trait;
use bytes::Bytes;
use futures::Stream;
use metrics::{counter, histogram};

use crate::driver::{
    BlobStorage, BoxReadStream, DriverState, Instance, SmallBlobStorage, StorageError,
    StreamingWriteError, WriteAttemptOps,
};
use crate::Digest;

const CANCELED_LABEL: &str = "canceled";
const OK_LABEL: &str = "ok";
const ERR_LABEL: &str = "err";

/// A `BlobStorage` that emits metrics for calls into an underlying `BlobStorage` implementation
#[derive(Clone, Debug)]
pub struct MetricsMonitoredStorage<BS> {
    driver_label: &'static str,
    purpose_label: &'static str,
    leaf_label: &'static str,
    inner: BS,
}

#[derive(Clone, Copy)]
enum Disposition {
    Incomplete,
    Complete,
    Error,
}

impl Disposition {
    fn label(&self) -> &'static str {
        match self {
            Disposition::Incomplete => CANCELED_LABEL,
            Disposition::Complete => OK_LABEL,
            Disposition::Error => ERR_LABEL,
        }
    }
}

struct ReadAttempt {
    driver_label: &'static str,
    purpose_label: &'static str,
    leaf_label: &'static str,
    instance: String,
    start_time: Instant,
    saw_first_byte: bool,
    disposition: Disposition,
    stream: BoxReadStream,
}

impl Stream for ReadAttempt {
    type Item = Result<Bytes, StorageError>;

    fn poll_next(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Option<Self::Item>> {
        let result = futures::ready!(Pin::new(&mut self.stream).poll_next(cx));

        match &result {
            Some(Ok(chunk)) => {
                if !self.saw_first_byte {
                    histogram!(
                        "toolchain_storage_time_to_first_byte_seconds",
                        self.start_time.elapsed(),
                        "operation" => "read",
                        "driver" => self.driver_label,
                        "purpose" => self.purpose_label,
                        "leaf" => self.leaf_label,
                        "reapi_instance" => self.instance.clone(),
                    );
                    self.saw_first_byte = true;
                }
                counter!(
                    "toolchain_storage_bytes_read_total",
                    chunk.len() as u64,
                    "driver" => self.driver_label,
                    "purpose" => self.purpose_label,
                    "leaf" => self.leaf_label,
                    "reapi_instance" => self.instance.clone(),
                );
            }
            Some(Err(_)) => {
                self.disposition = Disposition::Error;
            }
            None => {
                if matches!(self.disposition, Disposition::Incomplete) {
                    self.disposition = Disposition::Complete;
                }
            }
        }

        Poll::Ready(result)
    }
}

impl Drop for ReadAttempt {
    fn drop(&mut self) {
        let result_label = self.disposition.label();

        counter!(
            "toolchain_storage_requests_handled_total",
            1,
            "operation" => "read",
            "driver" => self.driver_label,
            "purpose" => self.purpose_label,
            "leaf" => self.leaf_label,
            "result" => result_label,
            "reapi_instance" => self.instance.clone(),
        );

        histogram!(
            "toolchain_storage_requests_handling_seconds",
            self.start_time.elapsed(),
            "operation" => "read",
            "driver" => self.driver_label,
            "purpose" => self.purpose_label,
            "leaf" => self.leaf_label,
            "result" => result_label,
            "reapi_instance" => self.instance.clone(),
        );
    }
}

struct WriteAttempt {
    driver_label: &'static str,
    purpose_label: &'static str,
    leaf_label: &'static str,
    instance: String,
    start_time: Instant,
    saw_first_byte: bool,
    disposition: Disposition,
    inner: Box<dyn WriteAttemptOps + Send + Sync + 'static>,
}

impl<BS> MetricsMonitoredStorage<BS> {
    pub fn new(
        inner: BS,
        driver_label: &'static str,
        purpose_label: &'static str,
        is_leaf: bool,
    ) -> Self {
        MetricsMonitoredStorage {
            driver_label,
            purpose_label,
            leaf_label: if is_leaf { "1" } else { "0" },
            inner,
        }
    }
}

#[async_trait]
impl<BS> BlobStorage for MetricsMonitoredStorage<BS>
where
    BS: BlobStorage + Send + Sync + 'static,
{
    async fn find_missing_blobs(
        &self,
        instance: Instance,
        digests: Vec<Digest>,
        state: DriverState,
    ) -> Result<Vec<Digest>, StorageError> {
        let instance_name = instance.name.clone();

        let start_time = Instant::now();

        counter!(
            "toolchain_storage_requests_started_total",
            1,
            "operation" => "find_missing_blobs",
            "driver" => self.driver_label,
            "purpose" => self.purpose_label,
            "leaf" => self.leaf_label,
            "reapi_instance" => instance_name.clone(),
        );

        counter!(
            "toolchain_storage_find_missing_blobs_total",
            digests.len() as u64,
            "driver" => self.driver_label,
            "purpose" => self.purpose_label,
            "leaf" => self.leaf_label,
            "reapi_instance" => instance_name.clone(),
        );
        let result = self
            .inner
            .find_missing_blobs(instance, digests, state)
            .await;

        counter!(
            "toolchain_storage_requests_handled_total",
            1,
            "operation" => "find_missing_blobs",
            "driver" => self.driver_label,
            "purpose" => self.purpose_label,
            "leaf" => self.leaf_label,
            "reapi_instance" => instance_name.clone(),
        );

        histogram!(
            "toolchain_storage_requests_handling_seconds",
            start_time.elapsed(),
            "operation" => "find_missing_blobs",
            "driver" => self.driver_label,
            "purpose" => self.purpose_label,
            "leaf" => self.leaf_label,
            "reapi_instance" => instance_name,
        );

        result
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
        let instance_name = instance.name.clone();
        let start_time = Instant::now();
        counter!(
            "toolchain_storage_requests_started_total",
            1,
            "operation" => "read",
            "driver" => self.driver_label,
            "purpose" => self.purpose_label,
            "leaf" => self.leaf_label,
            "reapi_instance" => instance_name.clone(),
        );

        let result = self
            .inner
            .read_blob(
                instance,
                digest,
                max_batch_size,
                read_offset,
                read_limit,
                state,
            )
            .await;

        match result {
            Ok(Some(stream)) => {
                let read_attempt = ReadAttempt {
                    stream,
                    saw_first_byte: false,
                    disposition: Disposition::Incomplete,
                    start_time,
                    driver_label: self.driver_label,
                    purpose_label: self.purpose_label,
                    leaf_label: self.leaf_label,
                    instance: instance_name.clone(),
                };
                Ok(Some(Box::pin(read_attempt) as BoxReadStream))
            }
            result => {
                counter!(
                    "toolchain_storage_requests_handled_total",
                    1,
                    "operation" => "read",
                    "driver" => self.driver_label,
                    "purpose" => self.purpose_label,
                    "leaf" => self.leaf_label,
                    "reapi_instance" => instance_name.clone(),
                );
                histogram!(
                    "toolchain_storage_requests_handling_seconds",
                    start_time.elapsed(),
                    "operation" => "read",
                    "driver" => self.driver_label,
                    "purpose" => self.purpose_label,
                    "leaf" => self.leaf_label,
                    "reapi_instance" => instance_name,
                );
                result
            }
        }
    }

    async fn begin_write_blob(
        &self,
        instance: Instance,
        digest: Digest,
        state: DriverState,
    ) -> Result<Box<dyn WriteAttemptOps + Send + Sync + 'static>, StreamingWriteError> {
        let instance_name = instance.name.clone();
        let start_time = Instant::now();
        counter!(
            "toolchain_storage_requests_started_total",
            1,
            "operation" => "write",
            "driver" => self.driver_label,
            "purpose" => self.purpose_label,
            "leaf" => self.leaf_label,
            "reapi_instance" => instance_name.clone(),
        );
        let attempt = self.inner.begin_write_blob(instance, digest, state).await?;

        let wrapped_attempt = WriteAttempt {
            driver_label: self.driver_label,
            purpose_label: self.purpose_label,
            leaf_label: self.leaf_label,
            instance: instance_name,
            start_time,
            saw_first_byte: false,
            disposition: Disposition::Incomplete,
            inner: attempt,
        };
        Ok(Box::new(wrapped_attempt))
    }

    fn ensure_instance(&mut self, instance: &Instance, state: DriverState) {
        self.inner.ensure_instance(instance, state)
    }
}

fn emit_write_metrics(
    duration: Duration,
    driver_label: &'static str,
    purpose_label: &'static str,
    leaf_label: &'static str,
    instance: String,
    disposition: Disposition,
) {
    let result_label = disposition.label();
    counter!(
        "toolchain_storage_requests_handled_total",
        1,
        "operation" => "write",
        "driver" => driver_label,
        "purpose" => purpose_label,
        "leaf" => leaf_label,
        "result" => result_label,
        "reapi_instance" => instance.clone(),
    );
    histogram!(
        "toolchain_storage_requests_handling_seconds",
        duration,
        "operation" => "write",
        "driver" => driver_label,
        "purpose" => purpose_label,
        "leaf" => leaf_label,
        "result" => result_label,
        "reapi_instance" => instance,
    );
}

#[async_trait]
impl WriteAttemptOps for WriteAttempt {
    async fn write(&mut self, batch: Bytes) -> Result<(), StreamingWriteError> {
        if !self.saw_first_byte {
            histogram!(
                "toolchain_storage_time_to_first_byte_seconds",
                self.start_time.elapsed(),
                "operation" => "write",
                "driver" => self.driver_label,
                "purpose" => self.purpose_label,
                "leaf" => self.leaf_label,
                "reapi_instance" => self.instance.clone(),
            );
            self.saw_first_byte = true;
        }

        counter!(
            "toolchain_storage_bytes_written_total",
            batch.len() as u64,
            "driver" => self.driver_label,
            "purpose" => self.purpose_label,
            "leaf" => self.leaf_label,
            "reapi_instance" => self.instance.clone(),
        );

        let result = self.inner.write(batch).await;
        if result.is_err() {
            self.disposition = Disposition::Error;
            emit_write_metrics(
                self.start_time.elapsed(),
                self.driver_label,
                self.purpose_label,
                self.leaf_label,
                self.instance.clone(),
                self.disposition,
            );
        }
        result
    }

    async fn commit(mut self: Box<Self>) -> Result<(), StreamingWriteError> {
        let WriteAttempt {
            inner,
            mut disposition,
            driver_label,
            purpose_label,
            leaf_label,
            start_time,
            instance,
            ..
        } = *self;

        let result = inner.commit().await;

        if matches!(disposition, Disposition::Incomplete) {
            disposition = match &result {
                Ok(_) => Disposition::Complete,
                Err(_) => Disposition::Error,
            };
        }
        emit_write_metrics(
            start_time.elapsed(),
            driver_label,
            purpose_label,
            leaf_label,
            instance,
            disposition,
        );

        result
    }
}

#[async_trait]
impl<BS> SmallBlobStorage for MetricsMonitoredStorage<BS>
where
    BS: SmallBlobStorage + Send + Sync + 'static,
{
    async fn find_missing_blobs(
        &self,
        instance: Instance,
        digests: Vec<Digest>,
        state: DriverState,
    ) -> Result<Vec<Digest>, StorageError> {
        let instance_name = instance.name.clone();

        let start_time = Instant::now();
        counter!(
            "toolchain_storage_requests_started_total",
            1,
            "operation" => "find_missing_blobs",
            "driver" => self.driver_label,
            "purpose" => self.purpose_label,
            "leaf" => self.leaf_label,
            "reapi_instance" => instance_name.clone(),
        );
        counter!(
            "toolchain_storage_find_missing_blobs_total",
            digests.len() as u64,
            "driver" => self.driver_label,
            "purpose" => self.purpose_label,
            "leaf" => self.leaf_label,
            "reapi_instance" => instance_name.clone(),
        );

        let result = self
            .inner
            .find_missing_blobs(instance, digests, state)
            .await;

        counter!(
            "toolchain_storage_requests_handled_total",
            1,
            "operation" => "find_missing_blobs",
            "driver" => self.driver_label,
            "purpose" => self.purpose_label,
            "leaf" => self.leaf_label,
            "reapi_instance" => instance_name.clone(),
        );
        histogram!(
            "toolchain_storage_requests_handling_seconds",
            start_time.elapsed(),
            "operation" => "find_missing_blobs",
            "driver" => self.driver_label,
            "purpose" => self.purpose_label,
            "leaf" => self.leaf_label,
            "reapi_instance" => instance_name,
        );
        result
    }

    async fn read_blob(
        &self,
        instance: Instance,
        digest: Digest,
        state: DriverState,
    ) -> Result<Option<Bytes>, StorageError> {
        let instance_name = instance.name.clone();

        let start_time = Instant::now();

        counter!(
            "toolchain_storage_requests_started_total",
            1,
            "operation" => "read",
            "driver" => self.driver_label,
            "purpose" => self.purpose_label,
            "leaf" => self.leaf_label,
            "reapi_instance" => instance_name.clone(),
        );
        let result = self.inner.read_blob(instance, digest, state).await;

        let disposition = match &result {
            Ok(_) => Disposition::Complete,
            Err(_) => Disposition::Error,
        };
        let result_label = disposition.label();

        counter!(
            "toolchain_storage_requests_handled_total",
            1,
            "operation" => "read",
            "driver" => self.driver_label,
            "purpose" => self.purpose_label,
            "leaf" => self.leaf_label,
            "result" => result_label,
            "reapi_instance" => instance_name.clone(),
        );

        histogram!(
            "toolchain_storage_requests_handling_seconds",
            start_time.elapsed(),
            "operation" => "read",
            "driver" => self.driver_label,
            "purpose" => self.purpose_label,
            "leaf" => self.leaf_label,
            "result" => result_label,
            "reapi_instance" => instance_name.clone(),
        );
        result
    }

    async fn write_blob(
        &self,
        instance: Instance,
        digest: Digest,
        content: Bytes,
        state: DriverState,
    ) -> Result<(), StorageError> {
        let instance_name = instance.name.clone();
        let start_time = Instant::now();

        counter!(
            "toolchain_storage_requests_started_total",
            1,
            "operation" => "write",
            "driver" => self.driver_label,
            "purpose" => self.purpose_label,
            "leaf" => self.leaf_label,
            "reapi_instance" => instance_name.clone(),
        );
        let result = self
            .inner
            .write_blob(instance, digest, content, state)
            .await;
        let duration = start_time.elapsed();

        let disposition = match &result {
            Ok(_) => Disposition::Complete,
            Err(_) => Disposition::Error,
        };
        let result_label = disposition.label();

        histogram!(
            "toolchain_storage_time_to_first_byte_seconds",
            duration,
            "operation" => "write",
            "driver" => self.driver_label,
            "purpose" => self.purpose_label,
            "leaf" => self.leaf_label,
            "reapi_instance" => instance_name.clone(),
        );

        counter!(
            "toolchain_storage_requests_handled_total",
            1,
            "operation" => "write",
            "driver" => self.driver_label,
            "purpose" => self.purpose_label,
            "leaf" => self.leaf_label,
            "result" => result_label,
            "reapi_instance" => instance_name.clone(),
        );

        histogram!(
            "toolchain_storage_requests_handling_seconds",
            duration,
            "operation" => "write",
            "driver" => self.driver_label,
            "purpose" => self.purpose_label,
            "leaf" => self.leaf_label,
            "result" => result_label,
            "reapi_instance" => instance_name,
        );
        result
    }
}
