# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import boto3

from toolchain.django.site.settings.base import *  # noqa: F401, F403
from toolchain.django.site.settings.db_config import DjangoDBDict, set_up_databases
from toolchain.pants_demos.depgraph.workflow.config import DepgraphWorkerConfig
from toolchain.util.secret.secrets_accessor_factories import get_secrets_reader
from toolchain.workflow.settings_extra_worker import *  # noqa: F401, F403

_use_remote_dbs = config.is_set("USE_REMOTE_DEV_DBS")
AWS_REGION = boto3.client("s3").meta.region_name
SECRETS_READER = get_secrets_reader(
    toolchain_env=TOOLCHAIN_ENV, is_k8s=IS_RUNNING_ON_K8S, use_remote_dbs=_use_remote_dbs, k8s_namespace=NAMESPACE
)

INSTALLED_APPS.append("toolchain.pants_demos.depgraph.apps.PantsDepgraphDemoApp")

# Set up databases.
# -----------------

# Django chokes if the 'default' isn't present at all, but it can be set to an empty dict, which
# will be treated as a dummy db.  A call to set_up_database() can override this with real db settings.
DATABASES: DjangoDBDict = {"default": {}}
DATABASE_ROUTERS = []  # type: ignore

set_up_databases(__name__, "pants_demos")

if IS_RUNNING_ON_K8S:
    DEPGRAPH_WORKER_CONFIG = DepgraphWorkerConfig.from_config(config)
else:
    DEPGRAPH_WORKER_CONFIG = DepgraphWorkerConfig.for_dev(namespace=NAMESPACE)

logger.info(f"depgraph worker config: {DEPGRAPH_WORKER_CONFIG}")
