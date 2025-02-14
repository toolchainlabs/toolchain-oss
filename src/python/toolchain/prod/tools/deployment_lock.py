# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

from toolchain.prod.tools.utils import Deployer
from toolchain.util.dynamodb_mutex.mutex import DynamoDbMutex, MutexTable


class DeploymentLock(DynamoDbMutex):
    _LOCK_REGION = "us-west-2"  # Similar to Terrafrom, our lock is currently "global" regardless of the region we are deploying into.
    _ENV = "prod-deploys"
    _DEPLOY_TIMEOUT = datetime.timedelta(minutes=90)

    @classmethod
    def setup_lock_table(cls) -> None:
        MutexTable(table_env=cls._ENV, aws_region=cls._LOCK_REGION).create_table()

    @classmethod
    def for_deploy(cls, deploy_category: str, deployer: Deployer) -> DeploymentLock:
        return cls(
            env=cls._ENV,
            name=deploy_category,
            holder=deployer.formatted_deployer,
            aws_region=cls._LOCK_REGION,
            timeout=cls._DEPLOY_TIMEOUT,
        )
