// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use digest::Digest;
use protos::build::bazel::remote::execution::v2::{Action as ActionRequest, ActionResult};
use protos::google::devtools::remoteworkers::v1test2::{BotSession, Lease, LeaseState};
use tokio::time::{sleep, timeout_at, Duration, Instant};

use crate::any_proto_encode;
use crate::server::{ActionStatus, Instance};

async fn execute(instance: &Instance, action_request: ActionRequest) -> ActionResult {
    let (_, mut receiver) = instance.execute(Digest::EMPTY, action_request);
    let deadline = Instant::now() + Duration::from_secs(10);
    loop {
        match &*receiver.borrow() {
            ActionStatus::Running(_) => {}
            ActionStatus::Completed(res) => return res.clone().unwrap(),
        }

        timeout_at(deadline, receiver.changed())
            .await
            .unwrap()
            .unwrap();
    }
}

fn complete_lease(lease: &mut Lease) {
    lease.result = Some(any_proto_encode(&ActionResult::default()));
    lease.state = LeaseState::Completed as i32;
    lease.status = Some(protos::google::rpc::Status {
        code: protos::google::rpc::Code::Ok as i32,
        ..Default::default()
    });
}

#[tokio::test]
async fn test_basic() {
    let instance = Instance::new("test".to_owned(), Duration::from_secs(60));

    // Spawn a worker that will execute the job.
    let instance2 = instance.clone();
    let worker = tokio::spawn(async move {
        let mut session = BotSession::default();

        // Wait for one job to arrive.
        instance2.poll(&mut session, Duration::from_secs(10)).await;
        assert_eq!(session.leases.len(), 1);

        // Then complete it.
        for lease in &mut session.leases {
            complete_lease(lease)
        }
        instance2
            .poll(&mut session, Duration::from_millis(10))
            .await;
    });

    // Then submit a job, and confirm that it completes.
    let _result = execute(&instance, ActionRequest::default()).await;

    worker.await.unwrap();
}

#[tokio::test]
async fn test_worker_expiration() {
    let expiration_timeout = Duration::from_secs(3);
    let instance = Instance::new("test".to_owned(), expiration_timeout);

    // Spawn a worker that will take a job with one session. Then, confirm that it takes longer
    // than the timeout for the work to be assigned to a second session.
    let instance2 = instance.clone();
    let worker = tokio::spawn(async move {
        let mut session = BotSession::default();
        session.name = "one".to_owned();

        // Wait for a job to arrive, but do not actually poll again on the session.
        instance2.poll(&mut session, Duration::from_secs(10)).await;
        assert_eq!(session.leases.len(), 1);

        // Then, wait a while, and poll in a new session.
        sleep(Duration::from_secs(1)).await;
        let mut session = BotSession::default();
        session.name = "two".to_owned();

        // Confirm that it takes some time for the job to be re-assigned.
        let poll_began = Instant::now();
        instance2.poll(&mut session, Duration::from_secs(6)).await;
        assert_eq!(session.leases.len(), 1);
        assert!(poll_began.elapsed() > Duration::from_secs(1));

        // Then complete it in the new session.
        for lease in &mut session.leases {
            complete_lease(lease)
        }
        instance2
            .poll(&mut session, Duration::from_millis(10))
            .await;
    });

    // Then submit a job, and confirm that it completes.
    let _result = execute(&instance, ActionRequest::default()).await;

    worker.await.unwrap();
}

#[tokio::test]
async fn test_action_cancellation() {
    let instance = Instance::new("test".to_owned(), Duration::from_secs(60));

    // Spawn a worker that will take a job, then sleep briefly and confirm that it has been
    // cancelled.
    let instance2 = instance.clone();
    let worker = tokio::spawn(async move {
        let mut session = BotSession::default();

        // Wait for a job to arrive.
        instance2.poll(&mut session, Duration::from_secs(10)).await;
        assert_eq!(session.leases.len(), 1);

        // Wait a while, and poll again to confirm that it has been cancelled, and that it
        // took a lot less than our poll timeout to return.
        sleep(Duration::from_secs(1)).await;
        let poll_timeout = Duration::from_secs(6);
        let poll_started = Instant::now();
        instance2.poll(&mut session, poll_timeout).await;
        assert_eq!(session.leases.len(), 0);
        assert!(poll_started.elapsed() < (poll_timeout / 4));
    });

    // Submit a job, but then cancel it shortly afterward.
    let (operation_name, _) = instance.execute(Digest::EMPTY, ActionRequest::default());
    sleep(Duration::from_secs(1)).await;
    instance.cancel(operation_name);

    worker.await.unwrap();
}
