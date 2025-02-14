// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

#![deny(warnings)]

use std::env;
use std::process::Stdio;
use std::time::Duration;

use regex::bytes::Regex;
use tokio::process::Command;

mod common;

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn redis_integration_test() {
    env_logger::init();

    // Create temporary directory for all test-related files.
    let config_dir_tmp = tempfile::tempdir().expect("create temp dir");
    let config_dir = config_dir_tmp.path();

    // Find `docker` on the PATH and skip the test if it is not found.
    // TODO: Configure CI to allow running Redis in some form.
    let paths = match env::var_os("PATH").map(|p| env::split_paths(&p).collect::<Vec<_>>()) {
        Some(xs) => xs,
        None => return,
    };
    let docker_path = match paths
        .iter()
        .map(|p| p.join("docker"))
        .find(|p| std::fs::metadata(p).is_ok())
    {
        Some(p) => p,
        None => return,
    };

    let is_ci = env::var_os("CIRCLECI").is_some();
    let _docker_redis = if !is_ci {
        // Pull the Docker image.
        let mut redis_image_pull = Command::new(docker_path.clone())
            .args(["pull", "redis:6.0.13"])
            .spawn()
            .expect("docker pull started");
        redis_image_pull
            .wait()
            .await
            .expect("docker pull succeeded");

        // Invoke a Docker container to run a Redis server.
        let mut redis_child = Command::new(docker_path)
            .args([
                "run",
                "-p",
                "6379:6379",
                "--rm",
                "--attach=STDOUT",
                "--attach=STDERR",
                "--init",
                "redis:6.0.13",
                "redis-server",
                "--loglevel",
                "debug",
            ])
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .stdin(Stdio::null())
            .spawn()
            .expect("docker started");

        // Wait for Redis to accept connections.
        let redis_output = redis_child.stdout.take().expect("redis stdout available");
        let redis_stderr = redis_child.stderr.take().expect("redis stderr available");
        let (redis_booted_sender, redis_booted) = tokio::sync::oneshot::channel::<()>();
        let redis_output_path = config_dir.join("redis_output.txt");
        tokio::spawn(common::scan_for_string_then_drain(
            redis_output,
            Regex::new("Ready to accept connections").expect("re"),
            redis_booted_sender,
            tokio::fs::File::create(redis_output_path.clone())
                .await
                .unwrap(),
            "redis",
        ));
        let redis_stderr_path = config_dir.join("redis_stderr.txt");
        tokio::spawn(common::drain_to_file(
            redis_stderr,
            tokio::fs::File::create(redis_stderr_path.clone())
                .await
                .unwrap(),
        ));
        let redis_guard = common::ProcessTerminationGuard(
            Some(redis_child),
            vec![redis_output_path.clone(), redis_stderr_path],
        );
        if let Err(_) = tokio::time::timeout(Duration::from_secs(5), redis_booted).await {
            panic!("Redis failed to boot.")
        }
        log::info!("Redis booted.");

        Some(redis_guard)
    } else {
        None
    };

    // Write the storage_server configuration file.
    let config_file = config_dir.join("config.yaml");
    let config_contents = r"
listen_address: 0.0.0.0:8980
redis_backends:
  main:
    address: 127.0.0.1:6379
    num_connections: 1
    enable_new_client: true
cas:
  redis_chunked:
    backend: main
    prefix: cas-
action_cache:
  redis_direct:
    backend: main
    prefix: ac-
";
    tokio::fs::write(config_file.clone(), config_contents.as_bytes())
        .await
        .expect("write config file");

    // Start the storage_server binary.
    let server_path = common::target_dir().join("storage_server");
    if tokio::fs::metadata(server_path.clone()).await.is_err() {
        panic!("storage_server binary not found.")
    }
    let mut server = Command::new(server_path)
        .arg("-c")
        .arg(config_file)
        .env("RUST_LOG", "info") // necessary for startup message to print
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("storage_server started");

    // Wait for storage_server to accept connections.
    let storage_output = server.stdout.take().expect("storage stdout available");
    let storage_stderr = server.stderr.take().expect("storage stderr available");
    let (storage_booted_sender, storage_booted) = tokio::sync::oneshot::channel::<()>();
    let storage_output_path = config_dir.join("storage_server_output.txt");
    let storage_stderr_path = config_dir.join("storage_server_stderr.txt");
    let _guard2 = common::ProcessTerminationGuard(
        Some(server),
        vec![storage_output_path.clone(), storage_stderr_path.clone()],
    );
    tokio::spawn(common::scan_for_string_then_drain(
        storage_output,
        Regex::new("Serving storage on").expect("re"),
        storage_booted_sender,
        tokio::fs::File::create(storage_output_path.clone())
            .await
            .unwrap(),
        "storage_server",
    ));
    tokio::spawn(common::drain_to_file(
        storage_stderr,
        tokio::fs::File::create(storage_stderr_path).await.unwrap(),
    ));
    if let Err(_) = tokio::time::timeout(Duration::from_secs(5), storage_booted).await {
        panic!("storage_server failed to boot.")
    }
    log::info!("storage_server booted.");

    // Run the integration test.
    common::run_integration_test("http://127.0.0.1:8980").await;
}
