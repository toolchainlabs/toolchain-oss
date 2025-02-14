# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json
import logging

from toolchain.kubernetes.application_api import KubernetesApplicationAPI, PodsInfos
from toolchain.prod.tools.secrets_rollout import Rollout, SecretRolloutHelper
from toolchain.util.secret.secrets_accessor import KubernetesSecretsAccessor

logger = logging.getLogger(__name__)


class DatabaseSecretRotator:
    """Manages the process of rotating a single secret."""

    def __init__(self, namespace: str, db_name: str) -> None:
        self._accessor = KubernetesSecretsAccessor.create_rotatable(namespace=namespace)
        self._secret_name = f"{namespace}-db-{db_name}-creds"  # See create_login_role()
        self._namespace = namespace
        self._db_name = db_name
        self._rollout_helper = SecretRolloutHelper(
            namespace=namespace, secret_name=self._secret_name, accessor=self._accessor
        )

    def propose_json_secret(self, json_secret: dict) -> None:
        rs = self._accessor.get_rotatable_secret(self._secret_name)
        logger.info(f"Propose new secret version: {self._secret_name}")
        rs.propose_value(json.dumps(json_secret))

    def promote_proposed_to_current(self) -> bool:
        rs = self._accessor.get_rotatable_secret(self._secret_name)
        logger.info(f"Promote proposed secret to current {self._secret_name}")
        return rs.promote_proposed_value_to_current()

    def get_master_creds_in_dev(self) -> dict:
        # Master DB creds are stored in k8s only in dev.
        return self._accessor.get_json_secret_or_raise(f"{self._namespace}-db-master-creds")

    def get_current_creds(self) -> dict:
        return self._accessor.get_json_secret_or_raise(self._secret_name)

    def _get_pods_for_db(self, namespace: str, db_name: str) -> PodsInfos:
        kubernetes = KubernetesApplicationAPI.for_pod(namespace)
        pods = kubernetes.get_pods_with_annotation("toolchain.com/databases", services="toolchain")
        return tuple(pod for pod in pods if db_name in pod.annotation.split(","))

    def _check_state(self) -> Rollout:
        pods = self._get_pods_for_db(self._namespace, self._db_name)
        return self._rollout_helper.check_secret_state(pods)

    def check_current_credentials_for_db(self) -> Rollout:
        rollout = self._check_state()
        logger.info(f"[{self._db_name}] {rollout}")
        return rollout

    def kill_unmatched_pod(self, rollout: Rollout) -> None:
        oldest_pod = sorted(rollout.not_matched, key=lambda pod: pod.uptime, reverse=True)[0]
        kubernetes = KubernetesApplicationAPI.for_pod(oldest_pod.namespace)
        kubernetes.delete_pod_by_name(oldest_pod.name)
        logger.info(
            f"[{self._db_name}] {rollout} deleted oldest pod: {oldest_pod}/{oldest_pod.name} uptime: {oldest_pod.uptime}"
        )
