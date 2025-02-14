// Copyright 2022 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

#[cfg(test)]
mod tests;

use std::collections::{hash_map, HashMap, HashSet, VecDeque};
use std::sync::{Arc, Weak};

use digest::Digest;
use parking_lot::{MappedMutexGuard, Mutex, MutexGuard};
use protos::build::bazel::remote::execution::v2::{
    execution_stage::Value as ExecutionStageValue, Action as ActionRequest, ActionResult,
    ExecuteOperationMetadata,
};
use protos::google::devtools::remoteworkers::v1test2::{BotSession, Lease, LeaseState};
use tokio::sync::watch;
use tokio::time::{sleep_until, timeout_at, Duration, Instant};
use tonic::{Code, Status};

use execution_util::{
    generate_operation_name, generate_uuid, InstanceName, OperationName, SessionName,
};

use crate::{any_proto_decode, any_proto_encode};

pub(crate) type ActionDigest = Digest;

type WorkerName = String;

type LeaseId = String;

#[derive(Debug, Clone)]
pub(crate) enum ActionStatus {
    Running(ExecuteOperationMetadata),
    Completed(Result<ActionResult, Status>),
}

impl ActionStatus {
    fn running(digest: ActionDigest, stage: ExecutionStageValue) -> Self {
        Self::Running(ExecuteOperationMetadata {
            stage: stage as i32,
            action_digest: Some(digest.into()),
            ..Default::default()
        })
    }
}

struct Action {
    digest: ActionDigest,
    request: ActionRequest,
    sender: watch::Sender<ActionStatus>,
    // TODO: Should (optionally) expire Operations.
    receivers: HashMap<OperationName, watch::Receiver<ActionStatus>>,
}

impl Action {
    fn new(
        initial_operation_name: OperationName,
        digest: ActionDigest,
        request: ActionRequest,
    ) -> (Self, watch::Receiver<ActionStatus>) {
        let (sender, receiver) =
            watch::channel(ActionStatus::running(digest, ExecutionStageValue::Queued));

        let mut receivers = HashMap::new();
        receivers.insert(initial_operation_name, sender.subscribe());

        let action = Action {
            digest,
            request,
            sender,
            receivers,
        };
        (action, receiver)
    }

    fn start(
        &self,
        actions: &Actions,
        actions_ref: Arc<Mutex<Actions>>,
        action_digest: ActionDigest,
    ) -> (Lease, RunningAction) {
        let lease = create_lease(&self.request);
        let running_action = RunningAction::new(lease.id.clone(), action_digest, actions_ref);
        running_action.update(actions, ExecutionStageValue::Executing);
        (lease, running_action)
    }
}

struct RunningAction {
    lease_id: LeaseId,
    digest: Option<ActionDigest>,
    actions: Arc<Mutex<Actions>>,
    start_time: Instant,
}

impl RunningAction {
    fn new(lease_id: LeaseId, digest: ActionDigest, actions: Arc<Mutex<Actions>>) -> Self {
        Self {
            lease_id,
            digest: Some(digest),
            actions,
            start_time: Instant::now(),
        }
    }

    fn is_cancelled(&self) -> bool {
        let Some(action_digest) = self.digest.as_ref() else {
            return true;
        };

        self.actions
            .lock()
            .all
            .get(action_digest)
            .map(|action| action.sender.is_closed())
            .unwrap_or(true)
    }

    fn update(&self, actions: &Actions, stage: ExecutionStageValue) {
        let Some(action_digest) = self.digest.as_ref() else { return };
        let Some(action) = actions.all.get(action_digest) else { return };

        log::info!(
            "[{}] Lease {} now in stage: {:?}",
            actions.instance_name,
            self.lease_id,
            stage,
        );

        let _ = action
            .sender
            .send(ActionStatus::running(*action_digest, stage));
    }

    /// Completes a RunningAction successfully with the given value.
    ///
    /// NB: Will fail loudly if called more than once.
    fn complete(&mut self, result: Result<ActionResult, Status>) {
        let action_digest = self.digest.take().unwrap();
        let instance_name = {
            let mut actions = self.actions.lock();
            if let Some(action) = actions.all.remove(&action_digest) {
                let _ = action.sender.send(ActionStatus::Completed(result));
            }
            actions.instance_name.clone()
        };

        let elapsed = self.start_time.elapsed();
        metrics::histogram!("toolchain_execution_actions_duration_seconds", elapsed, "bucket" => "complete", "customer_id" => instance_name);
    }
}

impl Drop for RunningAction {
    fn drop(&mut self) {
        let instance_name = {
            let actions = self.actions.lock();

            self.update(&actions, ExecutionStageValue::Queued);

            let Some(action_digest) = self.digest.take() else { return };
            actions
                .queued
                .send_modify(|queued| queued.push_front(action_digest));
            actions.instance_name.clone()
        };

        let elapsed = self.start_time.elapsed();
        metrics::histogram!("toolchain_execution_actions_duration_seconds", elapsed, "bucket" => "cancelled", "customer_id" => instance_name);
    }
}

struct Worker {
    instance: InstanceName,
    worker_name: WorkerName,
    session_name: SessionName,
    capacity: u16,
    leases: HashMap<LeaseId, (Lease, RunningAction)>,
    expiration: Instant,
}

impl Worker {
    fn new(
        instance: InstanceName,
        worker_name: WorkerName,
        session_name: SessionName,
        expiration_timeout: Duration,
    ) -> Self {
        Self {
            instance,
            session_name,
            worker_name,
            // TODO: `buildbox` does not put anything useful in the BotSession.worker struct about
            // the total capacity. But it could be encoded in a platform property.
            capacity: 1,
            leases: HashMap::new(),
            expiration: Instant::now() + expiration_timeout,
        }
    }

    fn extend_expiration(&mut self, timeout: Duration) {
        self.expiration = Instant::now() + timeout;
    }

    fn complete_and_remove_leases(&mut self, session: &mut BotSession) {
        session.leases.retain(|lease| {
            let lease_state = LeaseState::from_i32(lease.state);
            if !matches!(
                lease_state,
                Some(LeaseState::Completed | LeaseState::Cancelled)
            ) {
                return true;
            }

            // Send the lease result if there is still a receiver waiting for it.
            if let Some((_, mut running_action)) = self.leases.remove(&lease.id) {
                let status = lease
                    .status
                    .as_ref()
                    .map(|status| Status::new(Code::from_i32(status.code), &status.message))
                    .unwrap_or_else(|| Status::cancelled("Unknown status."));
                let result = if status.code() == Code::Ok {
                    any_proto_decode(lease.result.as_ref()).map_err(|e| {
                        Status::internal(format!("Failed to decode action result from lease: {e}"))
                    })
                } else {
                    Err(status)
                };
                running_action.complete(result);
            }

            // Remove the completed/cancelled lease.
            false
        })
    }

    /// If changes were made to the BotSession, then returns true.
    fn cancel_expired_and_maybe_add_new_leases(
        &mut self,
        actions_ref: &Arc<Mutex<Actions>>,
        session: &mut BotSession,
    ) -> bool {
        let mut session_changed = false;

        // Cancel any leases which the server is no longer tracking.
        session.leases.retain(|lease| {
            match self.leases.entry(lease.id.clone()) {
                hash_map::Entry::Occupied(oe) => {
                    if !oe.get().1.is_cancelled() {
                        // This lease is still valid.
                        return true;
                    }
                    oe.remove();
                }
                hash_map::Entry::Vacant(_) => {}
            }

            session_changed = true;
            false
        });

        // Create new leases for any Actions we can acquire.
        let actions = actions_ref.lock();
        let mut acquire_leases = self.capacity as usize - self.leases.len();
        actions.queued.send_if_modified(|queued| {
            let mut modified = false;
            while acquire_leases > 0 {
                // TODO: Constraints are not yet applied.
                //   see https://github.com/toolchainlabs/toolchain/issues/16850
                let Some(action_digest) = queued.pop_front() else {
                    break;
                };
                modified = true;

                let Some(action) = actions.all.get(&action_digest) else {
                    continue;
                };

                let (lease, running_action) =
                    action.start(&actions, actions_ref.clone(), action_digest);
                log::info!(
                    "[{}] Worker {} (session {}) acquiring lease {} for action {action_digest:?}",
                    self.instance,
                    self.worker_name,
                    self.session_name,
                    lease.id
                );
                session.leases.push(lease.clone());
                self.leases
                    .insert(lease.id.clone(), (lease, running_action));
                acquire_leases -= 1;
                session_changed = true
            }
            modified
        });

        session_changed
    }
}

struct Workers {
    instance_name: InstanceName,
    workers: Mutex<HashMap<SessionName, Worker>>,
    expiration_timeout: Duration,
}

impl Workers {
    fn new(instance_name: InstanceName, expiration_timeout: Duration) -> Arc<Self> {
        let workers = Arc::new(Self {
            instance_name,
            workers: Mutex::default(),
            expiration_timeout,
        });
        tokio::spawn(Self::worker_expiration_task(Arc::downgrade(&workers)));
        workers
    }

    async fn worker_expiration_task(workers: Weak<Workers>) {
        let mut next_deadline = Instant::now();
        loop {
            // Wait until the next worker expiration deadline.
            sleep_until(next_deadline).await;

            let Some(workers) = workers.upgrade() else {
                // The Instance is shutting down.
                return;
            };

            // Remove any workers which have expired, while updating our next_deadline to the minimum
            // deadline of surviving workers.
            let now = Instant::now();
            next_deadline = now + workers.expiration_timeout;
            workers.workers.lock().retain(|_session_name, worker| {
                if worker.expiration < now {
                    // Worker session has expired.
                    false
                } else {
                    if worker.expiration < next_deadline {
                        next_deadline = worker.expiration;
                    }
                    true
                }
            });
        }
    }

    /// Acquires exclusive access to a Worker with the given SessionName until the returned guard
    /// is dropped.
    fn worker(
        &self,
        worker_name: WorkerName,
        session_name: SessionName,
    ) -> MappedMutexGuard<Worker> {
        MutexGuard::map(self.workers.lock(), |workers| {
            workers.entry(session_name.clone()).or_insert_with(|| {
                Worker::new(
                    self.instance_name.clone(),
                    worker_name,
                    session_name,
                    self.expiration_timeout,
                )
            })
        })
    }

    fn update_gauges(&self) {
        let count = self.workers.lock().len();
        metrics::gauge!("toolchain_execution_workers_state", count as f64, "bucket" => "ok", "customer_id" => self.instance_name.clone());
    }
}

struct Actions {
    instance_name: InstanceName,
    all: HashMap<ActionDigest, Action>,
    queued: watch::Sender<VecDeque<ActionDigest>>,
}

impl Actions {
    fn new(instance_name: InstanceName) -> Arc<Mutex<Self>> {
        let (sender, _receiver) = watch::channel(VecDeque::new());
        Arc::new(Mutex::new(Self {
            instance_name,
            all: HashMap::default(),
            queued: sender,
        }))
    }

    fn update_gauges(&self) {
        let queued_digests: HashSet<ActionDigest> = self.queued.borrow().iter().cloned().collect();
        let (mut queued, mut executing) = (0, 0);
        for action_digest in self.all.keys() {
            if queued_digests.contains(action_digest) {
                queued += 1;
            } else {
                executing += 1;
            }
        }
        metrics::gauge!("toolchain_execution_actions_state", queued as f64, "bucket" => "queued", "customer_id" => self.instance_name.clone());
        metrics::gauge!("toolchain_execution_actions_state", executing as f64, "bucket" => "executing", "customer_id" => self.instance_name.clone());
    }
}

// NB: The Actions lock may be acquired under the Workers lock, but not the reverse.
#[derive(Clone)]
pub(crate) struct Instance {
    name: InstanceName,
    actions: Arc<Mutex<Actions>>,
    workers: Arc<Workers>,
}

impl Instance {
    fn new(name: InstanceName, expiration_timeout: Duration) -> Self {
        Self {
            name: name.clone(),
            actions: Actions::new(name.clone()),
            workers: Workers::new(name, expiration_timeout),
        }
    }

    pub(crate) fn execute(
        &self,
        action_digest: Digest,
        action_request: ActionRequest,
    ) -> (OperationName, watch::Receiver<ActionStatus>) {
        let operation_name = generate_operation_name(&self.name);
        let mut actions = self.actions.lock();
        let receiver = match actions.all.entry(action_digest) {
            hash_map::Entry::Occupied(mut oe) => {
                // Create a new receiver. Operation names must not collide, so we know that this
                // will be a brand new receiver.
                let receiver = oe.get().sender.subscribe();
                oe.get_mut()
                    .receivers
                    .insert(operation_name.clone(), receiver.clone());
                receiver
            }
            hash_map::Entry::Vacant(ve) => {
                let (action, receiver) =
                    Action::new(operation_name.clone(), action_digest, action_request);
                log::info!("[{}] Queueing new action for {action_digest:?}", self.name);
                ve.insert(action);
                actions
                    .queued
                    .send_modify(|queued| queued.push_back(action_digest));
                receiver
            }
        };

        (operation_name, receiver)
    }

    pub(crate) fn wait(
        &self,
        operation_name: &OperationName,
    ) -> Option<watch::Receiver<ActionStatus>> {
        // NB: Linear time. Consider indexing, or (encoding more information in the operation
        // name) if it shows up in profiles.
        self.actions
            .lock()
            .all
            .values()
            .find_map(|action| action.receivers.get(operation_name).cloned())
    }

    pub(crate) fn cancel(&self, operation_name: OperationName) {
        // NB: Linear time. Consider indexing, or (encoding more information in the operation
        // name) if it shows up in profiles.
        let mut actions = self.actions.lock();
        let mut actions_to_remove = Vec::new();
        for action in actions.all.values_mut() {
            action.receivers.remove(&operation_name);
            if action.sender.is_closed() {
                actions_to_remove.push(action.digest);
            }
        }
        for action_digest in actions_to_remove {
            actions.all.remove(&action_digest);
        }
    }

    pub(crate) async fn poll(&self, session: &mut BotSession, deadline_timeout: Duration) {
        let deadline = Instant::now() + deadline_timeout;

        // Finalize and remove any completed leases in the session.
        self.workers
            .worker(session.bot_id.clone(), session.name.clone())
            .complete_and_remove_leases(session);

        // Then, check if there are any new leases, and if not, wait for notification of a change.
        let mut actions_queued = self.actions.lock().queued.subscribe();
        loop {
            {
                let mut worker = self
                    .workers
                    .worker(session.bot_id.clone(), session.name.clone());
                worker.extend_expiration(self.workers.expiration_timeout);

                let session_changed =
                    worker.cancel_expired_and_maybe_add_new_leases(&self.actions, session);

                // If we made changes to the session, or the worker has ongoing leases to manage,
                // then don't wait for new leases to arrive, as it might delay completing the
                // existing work.
                if session_changed || !session.leases.is_empty() {
                    break;
                }
            }

            // Wait for any new leases outside the lock, but return immediately if we hit the
            // deadline.
            if timeout_at(deadline, actions_queued.changed())
                .await
                .is_err()
            {
                break;
            }
        }
    }

    fn update_gauges(&self) {
        self.workers.update_gauges();
        self.actions.lock().update_gauges();
    }
}

#[derive(Clone, Default)]
pub struct Instances {
    instances: Arc<Mutex<HashMap<InstanceName, Instance>>>,
}

impl Instances {
    pub(crate) fn instance(&self, name: InstanceName) -> Instance {
        self.instances
            .lock()
            .entry(name.clone())
            .or_insert_with(|| Instance::new(name, Duration::from_secs(60)))
            .clone()
    }

    /// Updates metrics gauges for all Instances.
    pub(crate) fn update_gauges(&self) {
        // Clone all Instances and then release the lock.
        let instances: Vec<Instance> = {
            let instances = self.instances.lock();
            instances.values().cloned().collect()
        };

        for instance in instances {
            instance.update_gauges();
        }
    }
}

fn generate_lease_id() -> LeaseId {
    generate_uuid()
}

fn create_lease(action: &ActionRequest) -> Lease {
    #[allow(deprecated)]
    Lease {
        id: generate_lease_id(),
        payload: Some(any_proto_encode(action)),
        result: None,
        state: LeaseState::Pending as i32,
        status: None,
        // TODO
        requirements: None,
        expire_time: None,
        // NB: We set allow(deprecated) above in order to set these. Using `..Default::default()`
        // would obscure new fields being added to the struct.
        assignment: "".to_owned(),
        inline_assignment: None,
    }
}
