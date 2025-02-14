# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from enum import Enum


class FakeKubernetesCluster(Enum):
    PROD = "yada-yada"
    DEV = "puffy-shirt"
    REMOTING = "festivus"
