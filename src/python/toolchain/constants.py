# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique

# We are not using a regular Enum since we want to 'extend' the env info object
# with more data, k8s namespace to be specific.
_ENVS_TYPES = dict(
    PROD="toolchain_prod", DEV="toolchain_dev", TEST="toolchain_test", COLLECTSTATIC="toolchain_collectstatic"
)
_ENV_TYPES_TO_NAMES = {val: key.lower() for key, val in _ENVS_TYPES.items()}


class _ToolchainEnvInfo:
    """Encapsulates run time environment information Environment type: dev, staging, prod, test, etc....

    Namespace name - when running in K8S.
    """

    def __init__(self, env: str, namespace: str | None = None, is_local: bool = False) -> None:
        if env not in _ENVS_TYPES.values():
            raise ValueError(f"Invalid env type {env}.")
        self._env_type = env
        self._namespace = namespace
        self._is_local = is_local

    def namespaced(self, namespace: str, is_local: bool) -> _ToolchainEnvInfo:
        return _ToolchainEnvInfo(self._env_type, namespace=namespace, is_local=is_local)

    @property
    def is_prod(self) -> bool:
        return self._env_type == _ENVS_TYPES["PROD"]

    @property
    def is_dev(self) -> bool:
        return self._env_type == _ENVS_TYPES["DEV"]

    @property
    def is_collect_static(self) -> bool:
        return self._env_type == _ENVS_TYPES["COLLECTSTATIC"]

    @property
    def namespace(self) -> str | None:
        return self._namespace

    @property
    def is_prod_namespace(self) -> bool:
        if self.is_dev:
            return False
        return self.namespace == "prod"

    @property
    def value(self) -> str:
        return self._env_type

    @property
    def is_prod_or_dev(self) -> bool:
        return self.is_dev or self.is_prod

    def get_env_name(self) -> str:
        """Returns returns a unique environment namethat allows isolating dev (and possible prod) environments by using
        the value returned here as a prefix for keys (for example)"""
        if self.is_dev:
            ns = self._namespace or ""
            return f"local-{ns}" if self._is_local else ns
        return _ENV_TYPES_TO_NAMES[self._env_type]

    def __str__(self) -> str:
        ns = f"/{self._namespace}" if self._namespace else ""
        return f"ToolchainEnv={self._env_type}{ns}"

    def __eq__(self, other) -> bool:
        return isinstance(other, _ToolchainEnvInfo) and (
            (self._env_type, self._namespace) == (other._env_type, other._namespace)
        )


ToolchainEnv = Enum("ToolchainEnv", names=_ENVS_TYPES, type=_ToolchainEnvInfo)  # type: ignore


@unique
class ToolchainServiceType(Enum):
    API = "api"
    WEB_UI = "web-ui"
    WEB_UI_MARKETING = "web-ui-marketing"
    ADMIN = "admin"
    WORKFLOW_WORKER = "worker"
    WORKFLOW_MAINTENANCE = "worker-maintenance"
    NA = "not-available"


@unique
class ServiceLocation(Enum):
    INTERNAL = "internal"
    EDGE = "edge"
    LOCAL = "local"


@dataclass(frozen=True)
class ToolchainServiceInfo:
    name: str
    location: ServiceLocation
    # because we don't want to expose service_type as an enum, just as a string right now.
    _type: ToolchainServiceType
    commit_sha: str | None = None

    @classmethod
    def for_local(cls, service_name: str) -> ToolchainServiceInfo:
        return cls(name=service_name, _type=ToolchainServiceType.NA, location=ServiceLocation.LOCAL)

    @classmethod
    def from_config(cls, service_name: str, config) -> ToolchainServiceInfo:
        service_type = ToolchainServiceType(config.get("TOOLCHAIN_SERVICE_TYPE"))
        if service_type == ToolchainServiceType.NA:
            raise ValueError("Invalid service type")
        location_str = config.get("TOOLCHAIN_SERVICE_LOCATION")
        location = ServiceLocation(location_str) if location_str else ServiceLocation.INTERNAL
        commit_sha = config.get("GIT_COMMIT_SHA")
        return cls(name=service_name, _type=service_type, location=location, commit_sha=commit_sha)

    @property
    def service_type(self) -> str:
        return self._type.value
