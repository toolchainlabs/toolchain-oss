// Copyright 2022 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

#![deny(warnings)]

use std::io::Write;
use std::path::PathBuf;

use clap::Parser;
use log::Level;
use tokio::fs::create_dir_all;

#[derive(Parser)]
#[command(name = "Toolchain Remote Execution Worker")]
#[command(author = "Toolchain Labs, Inc.")]
#[command(version = "0.0.1")]
#[command(about = "Spawns Toolchain Remote Execution worker processes.", long_about = None)]
struct WorkerCommand {
    /// Your Toolchain organization ID. You can find this by running
    /// `./pants auth-token-info --verbose` and looking at the key `toolchain_customer`, or by
    /// asking Toolchain for the value.
    #[arg(short, long, env, required = true)]
    org_id: String,
    /// The address to the remote execution controller. If grpcs is used (highly recommended), an
    /// auth token must be set; see `--auth-token-env-var-name`.
    #[arg(long, env, default_value = "grpcs://workers.toolchain.com:8981")]
    endpoint: String,
    /// The environment variable name to read for the auth token. This is used to authenticate to
    /// the `--endpoint`.
    ///
    /// If not set, will default to looking at the env var `AUTH_TOKEN`. If `AUTH_TOKEN` is set,
    /// then it will be used; else, the auth token mechanism will be ignored.
    #[arg(long, env)]
    auth_token_env_var_name: Option<String>,
    /// The log level to use for this process's own logging: `info`, `warn`, `error`, `debug`, or
    /// `trace`.
    #[arg(short, long, env, default_value = "info")]
    log_level: String,
    /// The number of workers processes to spawn. Each worker is able to execute one remote
    /// execution process at a time.
    #[arg(short, long, env, default_value_t = 1)]
    worker_concurrency: u16,
    /// How many seconds worker processes should wait before timing out requests.
    #[arg(long, env, default_value_t = 30)]
    request_timeout: u64,
    /// Where to create the cache for remote execution. The dir will be created if it does not
    /// yet exist.
    #[arg(long, env, default_value = "/toolchain/cache")]
    cache_directory: PathBuf,
    /// How much storage the cache can use. Expects a value in the format `30G`.
    #[arg(long, env, default_value = "30G")]
    max_cache_size: String,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cmd = WorkerCommand::parse();

    let log_level: Level = cmd.log_level.parse()?;
    stderrlog::new()
        .show_module_names(true)
        .timestamp(stderrlog::Timestamp::Second)
        .verbosity(log_level)
        .init()?;

    let cache_directory = {
        let d = cmd.cache_directory.as_path();
        log::debug!("Setting up cache directory at {}", d.display());
        create_dir_all(d).await?;
        d
    };

    let auth_token_file = {
        let maybe_token = match cmd.auth_token_env_var_name {
            Some(env_var) => {
                let res = std::env::var(&env_var).map_err(|e| {
                    format!(
                        "Issue evaluating the option `--auth-token-env-var-name={env_var}`: {e}"
                    )
                })?;
                Some(res)
            }
            // If the option is unset, use AUTH_TOKEN if defined. Else, don't use auth tokens.
            None => std::env::var("AUTH_TOKEN").ok(),
        };
        if let Some(token) = maybe_token {
            log::info!("Using auth token from environment variable");
            let mut file = tempfile::NamedTempFile::new()?;
            file.write_all(token.as_bytes())?;
            Some(file)
        } else {
            None
        }
    };

    let processes = worker::processes(
        &cmd.org_id,
        cmd.worker_concurrency,
        cmd.request_timeout,
        &cmd.endpoint,
        log_level,
        auth_token_file.as_ref(),
        cache_directory,
        &cmd.max_cache_size,
    );

    log::info!("Starting {} worker(s).", cmd.worker_concurrency);
    worker::spawn_and_manage_processes(processes).await?;

    Ok(())
}
