# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from dataclasses import dataclass
from enum import Enum, unique
from typing import Optional

import requests

from toolchain.base.toolchain_error import ToolchainAssertion, ToolchainError
from toolchain.kubernetes.application_api import PodInfo, PodsInfos
from toolchain.util.secret.secrets_accessor import SecretsAccessor

logger = logging.getLogger(__name__)

PodNames = tuple[str, ...]


class VersionNotFound(ToolchainError):
    pass


@unique
class RolloutState(Enum):
    """Secret rollout state labels."""

    COMPLETED = "COMPLETED"  # new version of the secret is fully rolled out (all pods have the expected version)
    PARTIAL = "PARTIAL"  # the new version of the secret is rolled out to some pods, but not all
    NOT_STARTED = "NOT_STARTED"  # no pods are using the new version of the secret

    @property
    def is_pending(self) -> bool:
        return self in [self.PARTIAL, self.NOT_STARTED]


@dataclass(frozen=True)
class Rollout:
    state: RolloutState
    pods: PodsInfos
    not_matched: PodsInfos

    @property
    def all_running(self) -> bool:
        return all(pod.is_running for pod in self.pods)

    @property
    def total_pods(self) -> int:
        return len(self.pods)

    @property
    def is_completed(self) -> bool:
        return self.state == RolloutState.COMPLETED

    def __str__(self) -> str:
        not_matched_names = ", ".join(pod.name for pod in self.not_matched)
        return f"rollout state: {self.state.value} to {len(self.not_matched)}/{self.total_pods}. not matched: {not_matched_names}"


class SecretRolloutHelper:
    _SECRETS_PATH = "/checksz/secretsz"

    State = RolloutState

    def __init__(self, namespace: str, secret_name: str, accessor: SecretsAccessor) -> None:
        self._namespace = namespace
        self._accessor = accessor
        self._secret_name = secret_name

    def check_secret_state(self, pods: PodsInfos) -> Rollout:
        if not pods:
            raise ToolchainAssertion("List of pods can't be empty.")
        expected_version = self._accessor.get_version(self._secret_name)
        logger.info(f"Secret: {self._secret_name} expected version: {expected_version} ({len(pods)} pods)")
        if not expected_version:
            raise VersionNotFound(f"no expected version for secret {self._secret_name} in namespace {self._namespace}")
        pod_to_versions = self._get_secrets_versions(pods, self._secret_name)
        logger.debug(f"[{self._secret_name}] pod to versions: {pod_to_versions}")
        if len(pod_to_versions) != len(pods):
            logger.warning(f"Some pods are missing expected secrets. ({len(pod_to_versions)}/{len(pods)})")
            # raise Error
        matched, not_matched_names = self._process_version_data(expected_version, pod_to_versions)
        if len(not_matched_names) == 0:
            return Rollout(state=RolloutState.COMPLETED, pods=pods, not_matched=tuple())
        not_matched = tuple(pod for pod in pods if pod.name in not_matched_names)
        rs = RolloutState.NOT_STARTED if len(matched) == 0 else RolloutState.PARTIAL
        return Rollout(state=rs, pods=pods, not_matched=not_matched)

    def _get_secrets_versions(self, pods: PodsInfos, secret_name: str) -> dict[str, str]:
        secret_versions = {}
        for pod_info in pods:
            secret_version = self._get_secret_version(pod_info, secret_name)
            if secret_version:
                secret_versions[pod_info.name] = secret_version
        return secret_versions

    def _get_secret_version(self, pod_info: PodInfo, secret_name: str) -> Optional[str]:
        # This is good when the code is running in a k8s cluster.
        # This class needs to support running this code outside the cluster and using the k8s api to proxy the api call to the correct pod
        # using KubernetesApplicationAPI.call_internal_endpoint
        url = pod_info.get_url(self._SECRETS_PATH)
        try:
            resp = requests.get(url, allow_redirects=False)
        except requests.RequestException as error:
            logger.warning(f"Failed to get secert from {pod_info.name}: {url} error: {error!r}")
            return None
        if resp.status_code != 200:  # Redirect is an error. the endpoint should always return 200.
            logger.warning(f"Failed to get secert from {pod_info.name}: {url} response: {resp}")
            return None
        return self._parse_secret_versions(resp.json(), secret_name, pod_info.name)

    def _parse_secret_versions(self, json_response: dict, secret_name: str, pod_name: str) -> Optional[str]:
        loaded_secrets = json_response["loaded"]
        secret_version = loaded_secrets.get(secret_name)
        if secret_version:
            return secret_version
        logger.warning(
            f"Failed to get secret {secret_name} from {pod_name}. known secrets: {sorted(loaded_secrets.keys())}"
        )
        return None

    def _process_version_data(
        self, expected_version: str, pod_to_versions: dict[str, str]
    ) -> tuple[PodNames, PodNames]:
        matched = []
        not_matched = []
        for pod_name, version in pod_to_versions.items():
            if version == expected_version:
                matched.append(pod_name)
            else:
                not_matched.append(pod_name)
        return tuple(matched), tuple(not_matched)
