# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import logging

from toolchain.kubernetes.constants import KubernetesCluster
from toolchain.kubernetes.secret_api import SecretAPI
from toolchain.util.secret.secrets_accessor import KubernetesSecretsAccessor, LocalSecretsAccessor

_logger = logging.getLogger(__name__)


class DatabaseSecretsHelper:
    @classmethod
    def for_local(cls, rotatable: bool = True) -> DatabaseSecretsHelper:
        return cls(LocalSecretsAccessor.create_rotatable() if rotatable else LocalSecretsAccessor())

    @classmethod
    def for_kubernetes(
        cls, namespace: str, cluster: KubernetesCluster | None = None, rotatable: bool = True
    ) -> DatabaseSecretsHelper:
        accessor = (
            KubernetesSecretsAccessor.create_rotatable(namespace=namespace, cluster=cluster)
            if rotatable
            else KubernetesSecretsAccessor.create(namespace=namespace, cluster=cluster)
        )
        return cls(accessor)

    def __init__(self, secrets_accessor):
        self._secrets_accessor = secrets_accessor

    def store_db_creds_if_not_exists(self, secret_name: str, creds: dict) -> None:
        if self._secrets_accessor.get_secret(secret_name) is None:
            self.store_db_creds(secret_name, creds)

    def store_db_creds(self, secret_name: str, creds: dict) -> None:
        """Stores a set of db creds in a secret.

        Updates any existing creds in that secret.
        """
        creds_secret_value = json.dumps(creds)
        self._secrets_accessor.set_secret(secret_name, creds_secret_value)
        _logger.info(f"Stored db creds in Secret {secret_name}")

    def get_db_creds(self, secret_name: str) -> dict | None:
        """Returns a set of db creds stored in a secret.

        Returns None if no such secret is found.
        """
        return self._secrets_accessor.get_json_secret(secret_name)


class SimpleDatabaseSecretsHelper:
    @classmethod
    def for_kubernetes(cls, cluster: KubernetesCluster, namespaces: tuple[str, ...]) -> SimpleDatabaseSecretsHelper:
        return cls(cluster, namespaces)

    def __init__(self, cluster: KubernetesCluster, namespaces: tuple[str, ...]) -> None:
        self._cluster = cluster
        self._namesapces = namespaces

    def store_db_creds(self, secret_name: str, creds: dict) -> None:
        for namespace in self._namesapces:
            secrets_api = SecretAPI.for_cluster(namespace=namespace, cluster=self._cluster)
            secrets_api.set_secret(secret_name, value_dict=creds)
            _logger.info(f"Stored simple db creds in Secret {secret_name} into {self._cluster.value}/{namespace}")
