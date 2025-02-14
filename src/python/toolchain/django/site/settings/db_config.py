# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
import sys
from collections.abc import Sequence
from typing import Any

from colors import cyan, green

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.constants import ToolchainEnv
from toolchain.django.db.db_router_registry import DBRouterRegistry
from toolchain.django.site.settings.util import maybe_prompt_k8s_port_fwd
from toolchain.util.net.net_util import hostname_resolves

logger = logging.getLogger(__name__)

DjangoDBDict = dict[str, dict[str, Any]]


def _db_from_creds(
    engine, user, password, set_role, host, port, dbname, disable_server_side_cursors=False, disable_ssl=False
):
    if engine == "postgres":
        django_engine = "django_prometheus.db.backends.postgresql"
    else:
        raise ToolchainAssertion(f"Unsupported engine: {engine}")

    db_creds = {
        "ENGINE": django_engine,
        "NAME": dbname,
        "USER": user,
        "PASSWORD": password,
        "SET_ROLE": set_role,
        "HOST": host,
        "PORT": port,
        "CONN_MAX_AGE": 3600,
        "DISABLE_SERVER_SIDE_CURSORS": disable_server_side_cursors,
    }
    if disable_ssl:
        db_creds["OPTIONS"] = {"sslmode": "disable"}
    return db_creds


# Validates that db creds contain all the required fields, and strips out any others.
# Allows us to ignore fields we don't know about in a secret.
def _filter_db_creds(**kwargs):
    ret = {}
    for key in ("engine", "user", "password", "set_role", "host", "port", "dbname"):
        ret[key] = kwargs[key]
    if "disable_server_side_cursors" in kwargs:
        ret["disable_server_side_cursors"] = kwargs["disable_server_side_cursors"]
    return ret


def direct_db(disable_ssl=False, **kwargs):
    db_kwargs = _filter_db_creds(**kwargs)
    return _db_from_creds(disable_ssl=disable_ssl, **db_kwargs)


# If accessing a remote db on kubernetes from a local machine, forward this local port to the remote db service.
_FORWARDED_DB_PORT = 5435


def prepare_database_dict(
    *, db_names: Sequence[str], toolchain_env: ToolchainEnv, secrets_reader, use_remote_dev_dbs: bool, namespace: str
) -> dict:
    """Set up the named databases.

    Service-specific settings files can call this to set up the databases they need.
    """
    db_dict = {}
    if use_remote_dev_dbs:
        _check_remote_dev_db_connectivity(namespace)
    for db_name in db_names:
        db_dict[db_name] = _set_up_database(
            db_name=db_name,
            is_prod=toolchain_env.is_prod,  # type: ignore[attr-defined]
            db_namespace=namespace,
            secrets_reader=secrets_reader,
            use_remote_dev_dbs=use_remote_dev_dbs,
        )
    return db_dict


def _check_remote_dev_db_connectivity(namespace: str) -> None:
    remote_hostname = f"{namespace}.{namespace}.svc.cluster.local"
    if not hostname_resolves(remote_hostname):
        print(cyan("To use remote dev dbs you must add the following line to your /etc/hosts:"))
        print(green(f"   127.0.0.1       {remote_hostname}"))
        input(cyan("Once you have done so, press enter to continue..."))
    maybe_prompt_k8s_port_fwd(
        local_port=_FORWARDED_DB_PORT,
        remote_port=5432,
        namespace=namespace,
        prompt="To use remote dev dbs you must create a tunnel to them:",
        service=f"{namespace}-db-postgresql",
    )


def _set_up_database(
    *, db_name: str, is_prod: bool, db_namespace: str, secrets_reader, use_remote_dev_dbs: bool
) -> dict:
    """Set up connection config for the given named database."""
    # Our dbs are set up with creds under these names.
    db_creds_name = f"{db_namespace}-db-{db_name}-creds".replace("_", "-")
    db_creds = secrets_reader.get_json_secret_or_raise(db_creds_name)
    db_host = db_creds["host"]
    logger.info(f"Connecting to db {db_creds_name} on {db_host}/{db_creds['dbname']}")
    # Disable SSL in prod, there seem to be an issue w/ RDS  Aurora Postgres
    db_info = direct_db(disable_ssl=is_prod, **db_creds)

    if use_remote_dev_dbs:
        # The creds contain the remote host:port, but we're accessing through a tunnel, so we must override.
        db_info.update({"HOST": "localhost", "PORT": _FORWARDED_DB_PORT})
    return db_info


def configure_database_connections(settings_module, db_names: tuple[str, ...]):
    # Set this in your local environment to use your dev dbs on Kubernetes instead of a local db.
    use_remote_requested = settings_module.config.is_set("USE_REMOTE_DEV_DBS") or settings_module.config.get(
        "DEV_NAMESPACE_OVERRIDE"
    )
    use_remote_dev_dbs = use_remote_requested and settings_module.TOOLCHAIN_ENV.is_dev  # type: ignore[attr-defined]
    if settings_module.IS_RUNNING_ON_K8S or use_remote_dev_dbs:
        namespace = settings_module.NAMESPACE
    else:
        namespace = "local"
    db_data = prepare_database_dict(
        db_names=db_names,
        toolchain_env=settings_module.TOOLCHAIN_ENV,
        secrets_reader=settings_module.SECRETS_READER,
        use_remote_dev_dbs=use_remote_dev_dbs,
        namespace=namespace,
    )
    settings_module.DATABASES.update(db_data)


def set_up_databases(module_name: str, *db_names):
    settings_module = sys.modules[module_name]
    if not settings_module.TOOLCHAIN_ENV.is_prod_or_dev:  # type: ignore[attr-defined]
        return
    configure_database_connections(settings_module, db_names)
    settings_module.DATABASE_ROUTERS[:] = DBRouterRegistry.get_routers(settings_module.SERVICE_INFO.name, db_names)  # type: ignore[attr-defined]
