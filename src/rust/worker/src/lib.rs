// Copyright 2022 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

#![deny(warnings)]

use std::path::Path;

use futures::future::try_join_all;
use log::Level;
use tokio::process::Command;
use tokio::time::{sleep, Duration};

// See:
// https://gitlab.com/BuildGrid/buildbox/buildbox-common/-/blob/7b4221a0a765c5d13645e1f7fa82d50e83a89d71/buildbox-common/buildboxcommon/buildboxcommon_logging.cpp#L29
fn log_level_to_buildbox_level(level: Level) -> &'static str {
    use Level::*;
    match level {
        // NB: `warn` needs remapping.
        Warn => "warning",
        Info => "info",
        Debug => "debug",
        Trace => "trace",
        Error => "error",
    }
}

#[derive(Clone, Debug)]
pub struct ProcessSpec {
    name: String,
    arg0: String,
    fixed_args: Vec<String>,
    args_factory: fn() -> Vec<String>,
}

impl ProcessSpec {
    fn args(&self) -> Vec<String> {
        [self.fixed_args.clone(), (self.args_factory)()].concat()
    }
}

/// Generate the list of processes which will be managed by the worker.
#[allow(clippy::too_many_arguments)]
pub fn processes(
    instance: &str,
    worker_concurrency: u16,
    worker_timeout: u64,
    workers_endpoint: &str,
    log_level: Level,
    auth_token: Option<&tempfile::NamedTempFile>,
    cache_location: &Path,
    cache_size: &str,
) -> Vec<ProcessSpec> {
    let buildbox_level = log_level_to_buildbox_level(log_level);
    let mut casd_args = vec![
        "--bind=127.0.0.1:50011".to_owned(),
        format!("--cas-remote={workers_endpoint}"),
        format!("--instance={instance}"),
        format!("--cas-instance={instance}"),
        format!("--quota-high={cache_size}"),
    ];
    if let Some(auth_token) = auth_token {
        casd_args.push(format!(
            "--cas-access-token={}",
            auth_token.path().display()
        ));
    }
    // The cache location as positional.
    casd_args.push(cache_location.display().to_string());

    let mut processes = vec![ProcessSpec {
        name: "casd".to_owned(),
        arg0: "buildbox-casd".to_owned(),
        fixed_args: casd_args,
        args_factory: Vec::new,
    }];

    processes.extend((0..worker_concurrency).map(|worker_num| {
        let mut args = vec![
            "--buildbox-run=buildbox-run-hosttools".to_owned(),
            "--cas-remote=http://127.0.0.1:50011".to_owned(),
            format!("--bots-remote={workers_endpoint}"),
            format!("--instance={instance}"),
            format!("--bots-request-timeout={worker_timeout}"),
            format!("--runner-arg=--log-level={buildbox_level}"),
            "--platform=OSFamily=linux".to_owned(),
            format!("--log-level={buildbox_level}"),
        ];

        if let Some(auth_token) = auth_token {
            args.push(format!(
                "--bots-access-token={}",
                auth_token.path().display()
            ));
        }

        ProcessSpec {
            name: format!("worker {worker_num}"),
            arg0: "buildbox-worker".to_owned(),
            fixed_args: args,
            // We generate a new BotId every time to avoid https://github.com/toolchainlabs/toolchain/issues/16405.
            // Note that this is a positional argument.
            args_factory: || vec![format!("worker-{}", uuid::Uuid::new_v4())],
        }
    }));

    processes
}

/// Spawns and parents the given list of processes, exiting for SIGINT or SIGTERM.
pub async fn spawn_and_manage_processes(processes: Vec<ProcessSpec>) -> Result<(), String> {
    let _ = try_join_all(
        processes
            .into_iter()
            .map(|p| tokio::spawn(spawn_and_manage_process(p)))
            .collect::<Vec<_>>(),
    )
    .await
    .map_err(|e| e.to_string())?;
    Ok(())
}

async fn spawn_and_manage_process(process_spec: ProcessSpec) {
    let mut iteration = 0u64;
    loop {
        // Spawn a copy of the process.
        let process = process_spec.clone();
        let mut child = Command::new(process.arg0.clone())
            .args(process.args())
            .stdin(std::process::Stdio::null())
            .kill_on_drop(true)
            .spawn()
            .unwrap_or_else(|e| {
                panic!("Failed to spawn {process_spec:?}: {e}");
            });

        let result = child.wait().await;

        // Delay, and then restart if it exits.
        let delay = Duration::from_secs(iteration.pow(2));
        iteration += 1;
        log::warn!(
            "Child process {} exited unexpectedly ({result:?}). Restarting in {} seconds...",
            process_spec.name,
            delay.as_secs()
        );
        sleep(delay).await;
    }
}
