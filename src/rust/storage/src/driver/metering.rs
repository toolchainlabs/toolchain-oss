// Copyright 2022 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::collections::HashMap;
use std::ops::{Add, AddAssign};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use async_trait::async_trait;
use bytes::Bytes;
use futures::StreamExt;
use serde::{Deserialize, Serialize};
use tokio::sync::mpsc::{unbounded_channel, UnboundedSender};
use tokio::task::JoinHandle;

use crate::driver::{
    BlobStorage, BoxReadStream, DriverState, Instance, StorageError, StreamingWriteError,
    WriteAttemptOps,
};
use crate::Digest;

/// A `BlobStorage` that emits metrics for calls into an underlying `BlobStorage` implementation
/// to enable metering of usage.
#[derive(Clone, Debug)]
pub struct MeteredStorage<BS> {
    sender: UnboundedSender<UsageReport>,
    inner: BS,
}

/// Usage report for cache. This is emitted by
#[derive(Clone, Default, Debug)]
pub struct UsageReport {
    customer_id: String,
    cache_read_bytes: usize,
    num_read_blobs: usize,
    cache_write_bytes: usize,
    num_write_blobs: usize,
}

impl AddAssign<&UsageReport> for UsageReport {
    fn add_assign(&mut self, rhs: &UsageReport) {
        self.cache_read_bytes += rhs.cache_read_bytes;
        self.num_read_blobs += rhs.num_read_blobs;
        self.cache_write_bytes += rhs.cache_write_bytes;
        self.num_write_blobs += rhs.num_write_blobs;
    }
}

impl<BS> MeteredStorage<BS> {
    pub fn new(inner: BS, sender: UnboundedSender<UsageReport>) -> Self {
        MeteredStorage { sender, inner }
    }
}

#[async_trait]
impl<BS> BlobStorage for MeteredStorage<BS>
where
    BS: BlobStorage + Send + Sync + 'static,
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
        let customer_id = instance.name.clone();

        let stream_opt = self
            .inner
            .read_blob(
                instance,
                digest,
                max_batch_size,
                read_offset,
                read_limit,
                state,
            )
            .await?;

        let mut stream = match stream_opt {
            Some(stream) => stream,
            None => return Ok(None),
        };

        let sender = self.sender.clone();
        let stream = async_stream::try_stream! {
            while let Some(chunk_result) = stream.next().await {
                let chunk = chunk_result?;
                let _ = sender.send(UsageReport {
                    customer_id: customer_id.clone(),
                    cache_read_bytes: chunk.len(),
                    ..UsageReport::default()
                });
                yield chunk;
            }
            let _ = sender.send(UsageReport {
                customer_id: customer_id.clone(),
                num_read_blobs: 1,
                ..UsageReport::default()
            });
        };

        let stream = Box::pin(stream) as BoxReadStream;

        Ok(Some(stream))
    }

    async fn begin_write_blob(
        &self,
        instance: Instance,
        digest: Digest,
        state: DriverState,
    ) -> Result<Box<dyn WriteAttemptOps + Send + Sync + 'static>, StreamingWriteError> {
        let customer_id = instance.name.clone();
        let attempt = self.inner.begin_write_blob(instance, digest, state).await?;
        let attempt = WriteAttempt {
            customer_id,
            sender: self.sender.clone(),
            attempt,
        };
        Ok(Box::new(attempt))
    }

    fn ensure_instance(&mut self, instance: &Instance, state: DriverState) {
        self.inner.ensure_instance(instance, state);
    }
}

struct WriteAttempt {
    customer_id: String,
    attempt: Box<dyn WriteAttemptOps + Send + Sync + 'static>,
    sender: UnboundedSender<UsageReport>,
}

#[async_trait]
impl WriteAttemptOps for WriteAttempt {
    async fn write(&mut self, batch: Bytes) -> Result<(), StreamingWriteError> {
        let _ = self.sender.send(UsageReport {
            customer_id: self.customer_id.clone(),
            cache_write_bytes: batch.len(),
            ..UsageReport::default()
        });
        self.attempt.write(batch).await
    }

    async fn commit(self: Box<Self>) -> Result<(), StreamingWriteError> {
        let customer_id = self.customer_id.clone();
        let sender = self.sender.clone();
        let result = self.attempt.commit().await;
        let _ = sender.send(UsageReport {
            customer_id,
            num_write_blobs: 1,
            ..UsageReport::default()
        });
        result
    }
}

/// Amberflo monitoring sink that aggregates and transmits meter events to Amberflo.
pub struct AmberfloEmitter {
    sender: UnboundedSender<UsageReport>,
    _actor_fut: JoinHandle<()>,
}

#[derive(Debug, Serialize, Deserialize, Eq, PartialEq)]
#[serde(rename_all = "camelCase")]
struct AmberfloIngestionEventDimensions {
    env: String,
}

#[derive(Debug, Serialize, Deserialize, Eq, PartialEq)]
#[serde(rename_all = "camelCase")]
struct AmberfloIngestionEvent {
    customer_id: String,
    meter_api_name: String,
    meter_value: usize,
    meter_time_in_millis: usize,
    dimensions: AmberfloIngestionEventDimensions,
}

impl AmberfloEmitter {
    pub fn new(
        aggregation_duration: Duration,
        id_prefix: String,
        env_dimension: String,
        api_key: String,
        api_ingest_url: Option<String>,
    ) -> Self {
        let (sender, mut receiver) = unbounded_channel::<UsageReport>();
        let api_ingest_url =
            api_ingest_url.unwrap_or_else(|| "https://app.amberflo.io/ingest".to_string());

        let actor_fut = tokio::spawn(async move {
            let client = reqwest::Client::new();
            let mut aggregated_usage_reports = HashMap::new();

            let mut continue_running = true;
            'OUTER: while continue_running {
                // TODO: Round this off to the nearest even multiple of the duration.
                let aggregation_window_ends = Instant::now().add(aggregation_duration);

                // Aggregate usage reports until the aggregation window ends.
                'INNER: loop {
                    tokio::select! {
                        usage_report_opt = receiver.recv() => {
                            let usage_report = match usage_report_opt {
                                Some(ur) => ur,
                                None => {
                                    // There are no more events. Mark that this loop is the
                                    // final loop and then break so that we can send the events.
                                    // This loop will not run again since we set `continue_running`
                                    // to false.
                                    continue_running = false;
                                    break 'INNER;
                                }
                            };
                            aggregated_usage_reports
                                .entry(usage_report.customer_id.clone())
                                .and_modify(|agg| *agg += &usage_report)
                                .or_insert(usage_report);
                        }
                        _ = tokio::time::sleep_until(aggregation_window_ends.into()) => {
                            break 'INNER;
                        }
                    }
                }

                // Go back into the aggregation loop if there are no records to send.
                if aggregated_usage_reports.is_empty() {
                    continue 'OUTER;
                }

                // Then transmit the usage reports to Amberflo for ingestion.
                let result = Self::emit_meter_events(
                    &client,
                    &id_prefix,
                    &api_key,
                    &api_ingest_url,
                    &aggregated_usage_reports,
                    &env_dimension,
                )
                .await;

                // On success, clear the aggregation buckets. Thus, on failure, keep them so
                // they are sent on a subsequent aggregation window.
                if result.is_ok() {
                    aggregated_usage_reports.clear();
                }
            }
        });

        AmberfloEmitter {
            sender,
            _actor_fut: actor_fut,
        }
    }

    pub fn sender(&self) -> UnboundedSender<UsageReport> {
        self.sender.clone()
    }

    async fn emit_meter_events(
        client: &reqwest::Client,
        id_prefix: &str,
        api_key: &str,
        api_ingest_url: &str,
        aggregated_usage_reports: &HashMap<String, UsageReport>,
        env_dimension: &str,
    ) -> Result<(), String> {
        let result = Self::emit_meter_events_inner(
            client,
            id_prefix,
            api_key,
            api_ingest_url,
            aggregated_usage_reports,
            env_dimension,
        )
        .await;
        let result_as_str = match &result {
            Ok(_) => "ok",
            Err(err) => {
                log::error!("Amberflo error: {:?}", err);
                "err"
            }
        };

        metrics::counter!("toolchain_storage_amberflo_requests_total", 1, "result" => result_as_str);
        result
    }

    async fn emit_meter_events_inner(
        client: &reqwest::Client,
        id_prefix: &str,
        api_key: &str,
        api_ingest_url: &str,
        aggregated_usage_reports: &HashMap<String, UsageReport>,
        env_dimension: &str,
    ) -> Result<(), String> {
        let meter_time_in_millis = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_millis();

        let records = aggregated_usage_reports
            .iter()
            .flat_map(|(customer_id, usage_report)| {
                vec![
                    AmberfloIngestionEvent {
                        customer_id: format!("{id_prefix}_{customer_id}"),
                        meter_api_name: "cache-read-bytes".to_string(),
                        meter_value: usage_report.cache_read_bytes,
                        meter_time_in_millis: meter_time_in_millis as usize,
                        dimensions: AmberfloIngestionEventDimensions {
                            env: env_dimension.to_string(),
                        },
                    },
                    AmberfloIngestionEvent {
                        customer_id: format!("{id_prefix}_{customer_id}"),
                        meter_api_name: "cache-num-read-blobs".to_string(),
                        meter_value: usage_report.num_read_blobs,
                        meter_time_in_millis: meter_time_in_millis as usize,
                        dimensions: AmberfloIngestionEventDimensions {
                            env: env_dimension.to_string(),
                        },
                    },
                    AmberfloIngestionEvent {
                        customer_id: format!("{id_prefix}_{customer_id}"),
                        meter_api_name: "cache-write-bytes".to_string(),
                        meter_value: usage_report.cache_write_bytes,
                        meter_time_in_millis: meter_time_in_millis as usize,
                        dimensions: AmberfloIngestionEventDimensions {
                            env: env_dimension.to_string(),
                        },
                    },
                    AmberfloIngestionEvent {
                        customer_id: format!("{id_prefix}_{customer_id}"),
                        meter_api_name: "cache-num-write-blobs".to_string(),
                        meter_value: usage_report.num_write_blobs,
                        meter_time_in_millis: meter_time_in_millis as usize,
                        dimensions: AmberfloIngestionEventDimensions {
                            env: env_dimension.to_string(),
                        },
                    },
                ]
            })
            .filter(|r| r.meter_value > 0)
            .collect::<Vec<_>>();

        if records.is_empty() {
            return Ok(());
        }

        let request = client
            .post(api_ingest_url)
            .header("Accept", "application/json")
            .header("x-api-key", api_key)
            .json(&records)
            .build()
            .map_err(|err| format!("Failed to build Amberflo request: {err}"))?;

        let result = client
            .execute(request)
            .await
            .map_err(|err| format!("Failed to send records to Amberflo: {err}"));

        match result {
            Ok(resp) if !resp.status().is_success() => {
                let status_code = resp.status().as_u16();
                let bytes = resp.bytes().await.map_err(|err| {
                    format!("Failed to read response body from Amberflo error: {err}")
                })?;
                let msg = String::from_utf8_lossy(&bytes);
                log::error!("Amberflo: Event not accepted: {} - {}", status_code, msg);
                return Err(format!(
                    "Amberflo did not accept meter event: {status_code}: {msg}"
                ));
            }
            Err(err) => {
                log::error!("Amberflo: Error while sending events: {err}");
                return Err(err);
            }
            _ => (),
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use std::cmp::Ordering;
    use std::convert::Infallible;
    use std::net::{Ipv4Addr, SocketAddr, SocketAddrV4};
    use std::sync::Arc;
    use std::time::Duration;

    use axum::body::{boxed, Body};
    use axum::http::{Request, Response};
    use axum::routing::Router;
    use hyper::server::conn::AddrIncoming;
    use parking_lot::Mutex;

    use super::{
        AmberfloEmitter, AmberfloIngestionEvent, AmberfloIngestionEventDimensions, UsageReport,
    };

    fn make_incoming() -> (AddrIncoming, SocketAddr) {
        let addr = SocketAddr::V4(SocketAddrV4::new(Ipv4Addr::LOCALHOST, 0));
        let incoming = AddrIncoming::bind(&addr).expect("failed to bind port");
        let local_addr = incoming.local_addr();
        (incoming, local_addr)
    }

    #[tokio::test]
    async fn ensure_amberflo_emitter_send_events() {
        // Spawn a Web server to capture Amerbflo emitted meters.
        let actual_amberflo_events = Arc::new(Mutex::new(Vec::new()));
        let actual_amberflo_events_2 = actual_amberflo_events.clone();
        let (capture_server_incoming, capture_server_local_addr) = make_incoming();
        let (received_request_sender, mut received_request_receiver) =
            tokio::sync::mpsc::unbounded_channel::<()>();
        tokio::spawn(async move {
            let app = Router::new().route_service(
                "/",
                tower::service_fn(move |request: Request<Body>| {
                    let actual_amberflo_events_2 = actual_amberflo_events_2.clone();
                    let received_request_sender = received_request_sender.clone();
                    async move {
                        actual_amberflo_events_2.lock().push(request);
                        received_request_sender.send(()).unwrap();
                        let response = Response::builder()
                            .status(200)
                            .body(boxed(Body::empty()))
                            .unwrap();
                        Ok::<_, Infallible>(response)
                    }
                }),
            );

            axum::Server::builder(capture_server_incoming)
                .serve(app.into_make_service())
                .await
                .unwrap();
        });

        let emitter = AmberfloEmitter::new(
            Duration::from_secs(2),
            "prefix".into(),
            "test".into(),
            "test-api-key".into(),
            Some(format!("http://{capture_server_local_addr}/")),
        );

        let sender = emitter.sender();
        sender
            .send(UsageReport {
                customer_id: "abc123".into(),
                cache_read_bytes: 1024,
                num_read_blobs: 1,
                ..UsageReport::default()
            })
            .unwrap();
        sender
            .send(UsageReport {
                customer_id: "def456".into(),
                cache_read_bytes: 1024,
                num_read_blobs: 1,
                ..UsageReport::default()
            })
            .unwrap();
        sender
            .send(UsageReport {
                customer_id: "abc123".into(),
                cache_read_bytes: 512,
                num_read_blobs: 1,
                ..UsageReport::default()
            })
            .unwrap();

        tokio::time::timeout(Duration::from_secs(5), received_request_receiver.recv())
            .await
            .map_err(|_| "Timed out while waiting for Amberflo emitter to send event.".to_string())
            .unwrap()
            .ok_or_else(|| "Receive error on channel from capture server.".to_string())
            .unwrap();

        let actual_events = actual_amberflo_events.lock().drain(..).collect::<Vec<_>>();
        let request = actual_events.into_iter().next().unwrap();
        let headers = request.headers();
        assert_eq!(headers.get("x-api-key").unwrap(), "test-api-key");

        let (_, body) = request.into_parts();
        let body_bytes = hyper::body::to_bytes(body).await.unwrap();
        let mut records: Vec<AmberfloIngestionEvent> = serde_json::from_slice(&body_bytes).unwrap();
        records.sort_by(|a, b| match a.customer_id.cmp(&b.customer_id) {
            Ordering::Equal => a.meter_api_name.cmp(&b.meter_api_name),
            ord => ord,
        });
        for record in &mut records {
            record.meter_time_in_millis = 0;
        }
        assert_eq!(
            records,
            vec![
                AmberfloIngestionEvent {
                    customer_id: "prefix_abc123".to_string(),
                    meter_time_in_millis: 0,
                    meter_api_name: "cache-num-read-blobs".to_string(),
                    meter_value: 2,
                    dimensions: AmberfloIngestionEventDimensions {
                        env: "test".to_string(),
                    }
                },
                AmberfloIngestionEvent {
                    customer_id: "prefix_abc123".to_string(),
                    meter_time_in_millis: 0,
                    meter_api_name: "cache-read-bytes".to_string(),
                    meter_value: 1536,
                    dimensions: AmberfloIngestionEventDimensions {
                        env: "test".to_string(),
                    }
                },
                AmberfloIngestionEvent {
                    customer_id: "prefix_def456".to_string(),
                    meter_time_in_millis: 0,
                    meter_api_name: "cache-num-read-blobs".to_string(),
                    meter_value: 1,
                    dimensions: AmberfloIngestionEventDimensions {
                        env: "test".to_string(),
                    }
                },
                AmberfloIngestionEvent {
                    customer_id: "prefix_def456".to_string(),
                    meter_time_in_millis: 0,
                    meter_api_name: "cache-read-bytes".to_string(),
                    meter_value: 1024,
                    dimensions: AmberfloIngestionEventDimensions {
                        env: "test".to_string(),
                    }
                },
            ]
        );
    }
}
