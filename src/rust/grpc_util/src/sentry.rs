// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::env;

use sentry::{types::Dsn, ClientInitGuard, ClientOptions};

use crate::infra::InfraConfig;

#[must_use = "Sentry client only operates if the init guard is kept alive."]
pub fn setup_sentry(config: Option<&InfraConfig>, service_name: &str) -> Option<ClientInitGuard> {
    if let Some(dsn) = config.and_then(|c| c.sentry_dsn.as_ref()) {
        let dsn: Dsn = dsn.parse().expect("parse Sentry DSN");

        let guard = sentry::init(ClientOptions {
            dsn: Some(dsn),
            release: sentry::release_name!(),
            environment: Some(
                env::var("K8S_POD_NAMESPACE")
                    .unwrap_or_else(|_| "local".to_owned())
                    .into(),
            ),
            send_default_pii: true,
            ..ClientOptions::default()
        });

        sentry::configure_scope(|scope| {
            scope.set_tag("service_name", service_name);
        });

        Some(guard)
    } else {
        // Panic if Sentry is not setup and the binary is running in staging/prod.
        match env::var_os("K8S_POD_NAMESPACE") {
            Some(namespace) if namespace == "staging" || namespace == "prod" => {
                panic!("Running on Kubernetes but Sentry is not enabled.")
            }
            _ => None,
        }
    }
}
