# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from enum import Enum

from toolchain.base.toolchain_error import ToolchainAssertion


class KubernetesCluster(Enum):
    PROD = "prod-e1-1"
    DEV = "dev-e1-1"
    REMOTING = "remoting-prod-e1-1"

    @property
    def is_dev_cluster(self) -> bool:
        return self == self.DEV


class KubernetesProdNamespaces:
    # namespaces for prod cluster, using constants and not an enum for now so it is easier to migrate to using this class.
    PROD = "prod"
    STAGING = "staging"
    EDGE = "edge"

    @classmethod
    def is_prod(cls, ns: str) -> bool:
        return ns == cls.PROD

    @classmethod
    def is_staging(cls, ns: str) -> bool:
        return ns == cls.STAGING


def get_namespaces_for_prod_cluster(cluster: KubernetesCluster) -> tuple[str, ...]:
    if cluster == KubernetesCluster.PROD:
        return KubernetesProdNamespaces.STAGING, KubernetesProdNamespaces.PROD
    if cluster == KubernetesCluster.REMOTING:
        return KubernetesProdNamespaces.STAGING, KubernetesProdNamespaces.PROD, KubernetesProdNamespaces.EDGE
    raise ToolchainAssertion(f"{cluster.value} is not a prod cluster")
