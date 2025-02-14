# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import random

from toolchain.django.site.settings.service import *  # noqa: F403
from toolchain.django.site.settings.util import MiddlewareAuthMode, get_middleware, get_rest_framework_config
from toolchain.lang.python.modules.module_distribution_map import ModuleDistributionMap
from toolchain.satresolver.pypi.depgraph import Depgraph
from toolchain.users.jwt.keys import JWTSecretData
from toolchain.util.leveldb.helpers import ensure_local_leveldb
from toolchain.util.leveldb.reloadable_dataset import ReloadableDataset

ROOT_URLCONF = "toolchain.service.dependency.api.urls"
REST_FRAMEWORK = get_rest_framework_config()
MIDDLEWARE = get_middleware(auth_mode=MiddlewareAuthMode.INTERNAL, with_csp=False)
INSTALLED_APPS.extend(
    [
        "django.contrib.auth",
        "toolchain.django.site",
        "toolchain.dependency.apps.DependencyAPIAppConfig",
        "toolchain.django.webresource.apps.WebResourceAppConfig",
        "toolchain.packagerepo.pypi.apps.PackageRepoPypiAppConfig",
        "toolchain.workflow.apps.WorkflowAppConfig",
    ]
)
AUTH_USER_MODEL = "site.ToolchainUser"
set_up_databases(__name__, "users", "pypi", "dependency")

# TODO: Generate data in a production bucket, under a production namespace.
_remote_base_dir_parent = "s3://pypi-dev.us-east-1.toolchain.com/shared/"

DEPGRAPH_BASE_DIR_URL = None
MODULE_DATA_BASE_DIR_URL = None
reload_period_secs = -1


JWT_AUTH_KEY_DATA = JWTSecretData.read_settings(TOOLCHAIN_ENV, SECRETS_READER)

if TOOLCHAIN_ENV.is_prod_or_dev:  # type: ignore[attr-defined]
    # We will eventually get rid of it, once we no longer use django sessions in this service
    SECRET_KEY = SECRETS_READER.get_secret_or_raise("django-secret-key")
    if IS_RUNNING_ON_K8S:
        DEPGRAPH_BASE_DIR_URL = config["DEPGRAPH_BASE_DIR_URL"]
        MODULE_DATA_BASE_DIR_URL = config["MODULE_DATA_BASE_DIR_URL"]
        reload_period_secs = 50 + random.randint(1, 40)  # nosec: B311
    else:
        # Ensure we have some local data, as we don't run a Watcher.
        _homedir = os.path.expanduser("~")
        _local_base_dir_parent = f"file:///{_homedir}/"
        DEPGRAPH_BASE_DIR_URL = ensure_local_leveldb(_local_base_dir_parent, _remote_base_dir_parent, "depgraph")
        MODULE_DATA_BASE_DIR_URL = ensure_local_leveldb(_local_base_dir_parent, _remote_base_dir_parent, "modules")
        # Don't run a reload thread, as it interferes with runserver's autoreload, and we're not running a Watcher
        # anyway, so we don't expect to see new data to reload.
        reload_period_secs = -1
else:
    SECRET_KEY = "depa-api-secret🧅key🫒"

if DEPGRAPH_BASE_DIR_URL is not None:
    DEPGRAPH = ReloadableDataset(Depgraph, DEPGRAPH_BASE_DIR_URL, reload_period_secs, start=not IS_RUNNING_ON_K8S)

if MODULE_DATA_BASE_DIR_URL is not None:
    MODULE_DISTRIBUTION_MAP = ReloadableDataset(
        ModuleDistributionMap, MODULE_DATA_BASE_DIR_URL, reload_period_secs, start=not IS_RUNNING_ON_K8S
    )
