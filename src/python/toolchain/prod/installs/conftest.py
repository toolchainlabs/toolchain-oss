# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from unittest import mock

import pytest

from toolchain.prod.installs.tests_helpers import FakeKubernetesCluster
from toolchain.util.prod.helm_client import HelmClient


#
# mock.patch("toolchain.util.prod.helm_client.KubernetesCluster", new=FakeKubernetesCluster
@pytest.fixture(autouse=True)
def _mock_helm():
    with mock.patch.object(HelmClient, "_HELM_EXECUTABLE", "no-op"), mock.patch.object(
        HelmClient, "Cluster", FakeKubernetesCluster
    ), mock.patch.object(HelmClient, "check_cluster_connectivity"):
        yield
