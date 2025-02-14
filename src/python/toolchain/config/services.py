# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import logging
from collections.abc import Hashable
from dataclasses import dataclass
from enum import Enum, unique
from pathlib import Path
from typing import Any, cast

import pkg_resources

from toolchain.base.frozendict import FrozenDict
from toolchain.base.memo import memoized
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.kubernetes.constants import KubernetesCluster

_logger = logging.getLogger(__name__)


SERVICE_GROUP_MARKER = "%"


@dataclass(frozen=True)
class BuildResult:
    revision: str
    commit_sha: str
    output: str | None = None


@unique
class ServiceType(Enum):
    GUNICORN = "gunicorn"
    WORKFLOW = "workflow"
    RUST = "rust"


@dataclass(frozen=True)
class ToolchainService:
    """The basic configuration for a toolchain service."""

    service_type: ServiceType
    service_name: str
    service_dir: Path
    service_config: FrozenDict[str, Hashable]
    cluster: KubernetesCluster  # for prod only.

    @property
    def name(self) -> str:
        return self.service_name.replace("/", "-")

    @property
    def ecr_repo_name(self) -> str | None:
        return None

    @property
    def chart_path(self) -> Path:
        return Path("services") / self.service_dir.as_posix().replace("_", "-") / self.service_name


@dataclass
class ServiceBuildResult:
    service: ToolchainService
    chart_parameters: tuple[str, ...]
    revision: str
    commit_sha: str
    output: str | None = None
    # For now it is a dict since we populate it and the tool/installer level.
    # later on we will switch to image builder doing all the work at which point
    # we can make this data class frozen and turn this in a Tuple[Tuple[str, str], ...]
    tests_images: dict[str, str] | None = None


@dataclass(frozen=True)
class KubernetesClusters:
    default_cluster_alias: str
    clusters: dict[str, dict]
    cluster_to_alias: dict[KubernetesCluster, str]

    @classmethod
    def from_config(cls, config: dict) -> KubernetesClusters:
        regions = config["regions"]
        if len(regions) > 1:
            raise ToolchainAssertion("Multuple regions not supported yet.")
        region_clusters: dict[str, dict] = tuple(regions.values())[0]["clusters"]

        default_clusters = [alias for alias, cluster in region_clusters.items() if cluster.get("default") is True]
        if not default_clusters:
            raise ToolchainAssertion("Default cluster not defined.")
        if len(default_clusters) > 1:
            raise ToolchainAssertion("Multiple default clusters defined. This is not supported.")
        cluster_to_alias = {KubernetesCluster(cluster["name"]): alias for alias, cluster in region_clusters.items()}
        return cls(
            default_cluster_alias=default_clusters[0], clusters=region_clusters, cluster_to_alias=cluster_to_alias
        )

    def _get_cluster_data(self, cluster_alias: str | None) -> dict:
        cluster_alias = cluster_alias or self.default_cluster_alias
        return self.clusters[cluster_alias]

    def get_cluster(self, alias: str | None) -> KubernetesCluster:
        return KubernetesCluster(self._get_cluster_data(alias)["name"])

    def get_channel(self, cluster: KubernetesCluster) -> str | None:
        alias = self.cluster_to_alias[cluster]
        return self._get_cluster_data(alias).get("notify_channel")


ServicesBuildResults = tuple[ServiceBuildResult, ...]


@dataclass(frozen=True)
class ToolchainNetworkService(ToolchainService):
    """The configuration for a toolchain network service."""

    dev_port: int
    """The dev port for this service.

    The dev port is the port that the service will serve on when run in a dev environment (e.g: via
    the `manage.py runserver` command). We pick different ports for each service so that we can run
    multiple services on the same dev machine at the same time, to test cross-service communication
    (e.g.: many services also need a users service running in order to work).

    Note that in the case of Django services, the dev ports aren't hard-coded in the settings modules
    themselves, for several reasons:
      - Django doesn't expect to manage its own serving port. In production it delegates this
        to WSGI, in dev to runserver, so it's conceptually wrong to hard-code these in settings.
      - We don't want manage.py to have to evaluate the entire Django settings just to set the args
        it passes to the runserver command.
      - In some cases a dev service will need to know the port of another dev service.
    """


class ToolchainPythonService(ToolchainService):
    """The configuration for a toolchain service implemented in Python."""

    _BASE_SERVICE_DIR = Path("src/python/toolchain/service/")

    @property
    def package(self) -> str:
        """Return this python service's package name."""
        package_relative = self.service_name.replace("-", "_").replace("/", ".")
        return f"toolchain.service.{package_relative}"

    def module(self, submodule_name: str) -> str:
        """Return the fully qualified module name for the given submodule of this python service."""
        return f"{self.package}.{submodule_name}"

    @property
    def chart_path(self) -> Path:
        return Path("services") / self.service_dir.as_posix().replace("_", "-") / self.name

    @property
    def _abs_service_dir(self) -> Path:
        return self._BASE_SERVICE_DIR.joinpath(self.service_dir)

    def get_pants_target(self, suffix: str | None = "") -> str:
        """Return a pants target address for one of this python service's top-level components.

        By default, return the service target itself.
        """
        return f"{self._abs_service_dir}:{self.name}{suffix}"

    @property
    def pants_target(self) -> str:
        return self.get_pants_target()


class ToolchainGunicornService(ToolchainNetworkService, ToolchainPythonService):
    """The configuration for a toolchain Django service running under gunicorn."""

    @property
    def pants_target(self) -> str:
        return self.get_pants_target(suffix="-gunicorn")

    @property
    def ecr_repo_name(self) -> str:
        return f"{self.service_name}/gunicorn"

    @property
    def has_static_files(self) -> bool:
        return cast(bool, self.service_config.get("has_static_files", False))


class ToolchainWorkflowService(ToolchainNetworkService, ToolchainPythonService):
    @property
    def maintenance_ecr_repo_name(self) -> str:
        return f"{self.service_name}/maintenance"

    @property
    def worker_ecr_repo_name(self) -> str:
        return f"{self.service_name}"

    @property
    def worker_pants_target(self) -> str:
        return self.get_pants_target("-worker")

    @property
    def worker_maintenance_pants_target(self) -> str:
        return self.get_pants_target("-maintenance")

    @property
    def pants_target(self) -> str:
        return self.worker_pants_target


class ToolchainRustService(ToolchainService):
    @property
    def binary_name(self) -> str:
        return self.service_name.replace("-", "_")

    @property
    def ecr_repo_name(self) -> str:
        return (self.service_dir / self.binary_name).as_posix()

    @property
    def docker_path(self) -> str:
        # Hack while we have buildbarn stuff, we can move things around once we get rid of buildbarn and buildfarm.
        name = self.service_name
        if self.service_dir.as_posix() in name:
            name = name.rsplit("-", maxsplit=1)[-1]
        return (self.service_dir / name).as_posix()

    @property
    def chart_path(self) -> Path:
        return Path("services") / self.service_dir.as_posix().replace("_", "-") / self.service_name


_SERVICE_TYPE_MAP = {
    ServiceType.GUNICORN: ToolchainGunicornService,
    ServiceType.WORKFLOW: ToolchainWorkflowService,
    ServiceType.RUST: ToolchainRustService,
}


@memoized
def get_service_config() -> dict[str, Any]:
    return json.loads(pkg_resources.resource_string(__name__, "services.json"))


def get_region_for_cluster(cluster_name: str) -> str:
    """Return the region of the named cluster."""
    service_config = get_service_config()
    for region, region_data in service_config["regions"].items():
        for cluster in region_data["clusters"].values():
            if cluster["name"] == cluster_name:
                return region
    raise ToolchainAssertion(f"No cluster named {cluster_name} found in services.json.")


class UnregisteredServiceError(ToolchainAssertion):
    """Indicates the requested service is not registered."""


def get_service(service_name: str) -> ToolchainService:
    config = get_service_config()
    clusters = KubernetesClusters.from_config(config)
    for service in config["services"]:
        if service_name == service["name"]:
            return _create_service(service, clusters.get_cluster(service.get("cluster")))
    raise UnregisteredServiceError(f"Service {service_name} not registered in services.json.")


def get_channel_for_cluster(cluster: KubernetesCluster) -> str | None:
    config = get_service_config()
    clusters = KubernetesClusters.from_config(config)
    return clusters.get_channel(cluster)


class ServiceTypeError(ToolchainAssertion):
    """Indicates the requested service type does not match the actual service type."""


def get_network_service(service_name: str) -> ToolchainNetworkService:
    service = get_service(service_name)
    if not isinstance(service, ToolchainNetworkService):
        raise ServiceTypeError(f"Expected a ToolchainNetworkService for {service_name!r}, got {service}.")
    return service


def get_gunicorn_service(service_name: str) -> ToolchainGunicornService:
    service = get_service(service_name)
    if not isinstance(service, ToolchainGunicornService):
        raise ServiceTypeError(f"Expected a ToolchainGunicornService for {service_name!r}, got {service}.")
    return service


def get_workflow_service(service_name: str) -> ToolchainWorkflowService:
    service = get_service(service_name)
    if not isinstance(service, ToolchainWorkflowService):
        raise ServiceTypeError(f"Expected a ToolchainWorkflowService for {service_name!r}, got {service}.")
    return service


def extrapolate_services(services_specs: list[str]) -> list[ToolchainService]:
    if not services_specs:
        raise ToolchainAssertion("Empty service spec.")
    services: set[ToolchainService] = set()
    config = get_service_config()
    clusters = KubernetesClusters.from_config(config)
    services_cfgs = config["services"]
    for service_spec in services_specs:
        services.update(_get_services_for_spec(service_spec, services_cfgs, clusters))
    return sorted(services, key=lambda service: service.service_name)


def _get_services_for_spec(
    service_spec: str, services_config: list[dict], clusters: KubernetesClusters
) -> list[ToolchainService]:
    services = []
    for service_cfg in services_config:
        cluster = clusters.get_cluster(service_cfg.get("cluster"))
        if service_spec.startswith(SERVICE_GROUP_MARKER) and service_spec[1:] in service_cfg.get("alias_groups", []):
            services.append(_create_service(service_cfg, cluster))
        elif service_cfg["name"].startswith(service_spec) and service_cfg.get("enabled", True):
            services.append(_create_service(service_cfg, cluster))
    if not services:
        raise ToolchainAssertion(f"No services matching: {service_spec}")
    return services


def extrapolate_python_services(
    service_specs: list[str],
) -> tuple[ToolchainGunicornService | ToolchainWorkflowService, ...]:
    services = extrapolate_services(service_specs)
    python_services = tuple(
        svc for svc in services if isinstance(svc, (ToolchainGunicornService, ToolchainWorkflowService))
    )
    non_python_services = sorted(svc.name for svc in set(services) - set(python_services))
    if non_python_services:
        _logger.warning(
            f'Skipping non-python services: {", ".join(non_python_services)} found '
            f'scanning {", ".join(service_specs)}.'
        )
    return python_services


def _create_service(service: dict[str, Any], cluster: KubernetesCluster) -> ToolchainService:
    service_type = ServiceType(service["type"])
    service_class: type[ToolchainService] = _SERVICE_TYPE_MAP[service_type]
    service_name = service["name"]
    service_dir = Path(service.get("service_dir", service_name.replace("-", "_")))
    service_config = FrozenDict.freeze_json_obj(service.get("config", {}))
    if issubclass(service_class, ToolchainNetworkService):
        dev_port = service["dev_port"]
        return service_class(
            service_type=service_type,
            service_name=service_name,
            service_dir=service_dir,
            cluster=cluster,
            dev_port=dev_port,
            service_config=service_config,
        )
    return service_class(
        service_type=service_type,
        service_name=service_name,
        service_dir=service_dir,
        cluster=cluster,
        service_config=service_config,
    )
