# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

import boto3

from toolchain.django.site.settings.base import *  # noqa: F403
from toolchain.django.site.settings.db_config import (  # noqa: F401  # pylint: disable=unused-import
    DjangoDBDict,
    set_up_databases,
)
from toolchain.util.secret.secrets_accessor_factories import get_secrets_reader

logger = logging.getLogger(__name__)


# Basic settings.
# ---------------

# This will return the region boto3 is configured to talk to.
# On Kubernetes, this should be the region we're running in, unless something horrible has gone wrong.
# On your local machine this is the region your awscli, and boto3, is configured to talk to, which is
# almost certainly the one we want here.
AWS_REGION = boto3.client("s3").meta.region_name


_use_remote_dbs = config.is_set("USE_REMOTE_DEV_DBS")
SECRETS_READER = get_secrets_reader(
    toolchain_env=TOOLCHAIN_ENV, is_k8s=IS_RUNNING_ON_K8S, use_remote_dbs=_use_remote_dbs, k8s_namespace=NAMESPACE
)


# Set up databases.
# -----------------

# Django chokes if the 'default' isn't present at all, but it can be set to an empty dict, which
# will be treated as a dummy db.  A call to set_up_database() can override this with real db settings.
DATABASES: DjangoDBDict = {"default": {}}
DATABASE_ROUTERS = []  # type: ignore


# Basic apps shared by all our binaries.
# --------------------------------------
COMMON_APPS = (
    "django.contrib.contenttypes",
    "django.contrib.postgres",  # For full-text search.
    "django_extensions",
    "toolchain.django.postgres_setrole.setrole.DjangoPostgreSQLSetRoleApp",
    # Note that DjangoPostgreSQLSetRoleApp must precede django_prometheus, since the latter opens database connections
    # in its ready() method, and those connections must SET ROLE.
    "django_prometheus",
    "rest_framework",
)

INSTALLED_APPS.extend(COMMON_APPS)
