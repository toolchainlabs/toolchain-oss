# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import cast

import pytest
from django.test import override_settings

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.config.endpoints import get_gunicorn_service_endpoint
from toolchain.config.services import (
    ServiceType,
    ServiceTypeError,
    ToolchainGunicornService,
    ToolchainNetworkService,
    ToolchainRustService,
    ToolchainService,
    ToolchainWorkflowService,
    UnregisteredServiceError,
    extrapolate_python_services,
    extrapolate_services,
    get_gunicorn_service,
    get_network_service,
    get_service,
    get_service_config,
)


def test_get_dev_port_for_network_service() -> None:
    assert get_network_service("servicerouter").dev_port == 9500
    assert get_network_service("users/api").dev_port == 9011
    assert get_network_service("users/ui").dev_port == 9010


def test_get_unknown_service() -> None:
    with pytest.raises(UnregisteredServiceError):
        get_service("streetsmarts")


def test_get_network_service() -> None:
    assert get_service("users/ui") == get_network_service("users/ui")


def test_get_gunicorn_service() -> None:
    assert get_service("users/ui") == get_gunicorn_service("users/ui")
    with pytest.raises(ServiceTypeError):
        get_gunicorn_service("proxy-server")


@override_settings(ROOT_URLCONF="toolchain.servicerouter.urls", IS_RUNNING_ON_K8S=True, NAMESPACE="jjbittenbinder")
def test_get_gunicorn_service_endpoint_k8s(settings) -> None:
    assert (
        get_gunicorn_service_endpoint(settings, "buildsense/api")
        == "http://buildsense-api.jjbittenbinder.svc.cluster.local:80/"
    )
    assert (
        get_gunicorn_service_endpoint(settings, "dependency/api")
        == "http://dependency-api.jjbittenbinder.svc.cluster.local:80/"
    )
    assert (
        get_gunicorn_service_endpoint(settings, "users/api") == "http://users-api.jjbittenbinder.svc.cluster.local:80/"
    )
    assert get_gunicorn_service_endpoint(settings, "users/ui") == "http://users-ui.jjbittenbinder.svc.cluster.local:80/"
    with pytest.raises(UnregisteredServiceError):
        get_gunicorn_service_endpoint(settings, "streetsmarts")


@override_settings(ROOT_URLCONF="toolchain.servicerouter.urls", IS_RUNNING_ON_K8S=False)
def test_get_gunicorn_service_endpoint_local(settings) -> None:
    assert get_gunicorn_service_endpoint(settings, "buildsense/api") == "http://localhost:9042/"
    assert get_gunicorn_service_endpoint(settings, "dependency/api") == "http://localhost:9071/"
    assert get_gunicorn_service_endpoint(settings, "users/api") == "http://localhost:9011/"
    assert get_gunicorn_service_endpoint(settings, "users/ui") == "http://localhost:9010/"
    with pytest.raises(UnregisteredServiceError):
        get_gunicorn_service_endpoint(settings, "streetsmarts")


def test_duplicate() -> None:
    services = get_service_config()["services"]

    names = {svc["name"] for svc in services}
    assert len(names) == len(services)

    network_services = [
        cast(ToolchainNetworkService, get_service(name))
        for name in names
        for service in services
        if isinstance(service, ToolchainNetworkService)
    ]
    ports = {svc.dev_port for svc in network_services}
    assert len(ports) == len(network_services)


def assert_services_and_types(
    *service_and_expected_types: tuple[str, type[ToolchainService]], services: Iterable[ToolchainService]
) -> None:
    expected_services_and_types = [(svc, type(svc)) for svc in services]
    services_and_types = [
        (get_service(service_name), service_type) for (service_name, service_type) in service_and_expected_types
    ]
    assert expected_services_and_types == services_and_types


def test_extrapolate() -> None:
    assert_services_and_types(
        ("buildsense/api", ToolchainGunicornService),
        ("buildsense/workflow", ToolchainWorkflowService),
        ("proxy-server", ToolchainRustService),
        ("toolshed", ToolchainGunicornService),
        ("users/ui", ToolchainGunicornService),
        services=extrapolate_services(
            [
                "users/ui",
                "toolshed",
                "buildsense",
                "proxy-server",
            ]
        ),
    )


def test_extrapolate_with_dashes() -> None:
    services = extrapolate_services(["scm-integration"])
    assert len(services) == 2
    api_svc = services[0]
    assert isinstance(api_svc, ToolchainGunicornService)

    assert api_svc.service_type == ServiceType.GUNICORN
    assert api_svc.service_name == "scm-integration/api"
    assert api_svc.service_dir.as_posix() == "scm_integration/api"
    assert api_svc.pants_target == "src/python/toolchain/service/scm_integration/api:scm-integration-api-gunicorn"
    workflow_svc = services[1]
    assert isinstance(workflow_svc, ToolchainWorkflowService)
    assert workflow_svc.service_type == ServiceType.WORKFLOW
    assert workflow_svc.service_name == "scm-integration/workflow"
    assert workflow_svc.service_dir.as_posix() == "scm_integration/workflow"
    assert (
        workflow_svc.pants_target
        == "src/python/toolchain/service/scm_integration/workflow:scm-integration-workflow-worker"
    )


def test_extrapolate_django() -> None:
    services = extrapolate_python_services(["users/ui", "proxy-server", "buildsense", "toolshed"])
    assert_services_and_types(
        ("buildsense/api", ToolchainGunicornService),
        ("buildsense/workflow", ToolchainWorkflowService),
        ("toolshed", ToolchainGunicornService),
        ("users/ui", ToolchainGunicornService),
        services=services,
    )


def test_extrapolate_invalid() -> None:
    with pytest.raises(ToolchainAssertion, match="No services matching: streetsmarts"):
        extrapolate_services(["users/ui", "proxy-server", "toolshed", "streetsmarts"])


def test_extrapolate_groups() -> None:
    services = extrapolate_services(["%prod"])
    assert {True, False} == {
        service.has_static_files for service in services if isinstance(service, ToolchainGunicornService)
    }
    assert [svc.service_name for svc in services] == [
        "buildsense/api",
        "payments/api",
        "scm-integration/api",
        "servicerouter",
        "toolshed",
        "users/api",
        "users/ui",
        "webhooks",
    ]


def test_extrapolate_multiple_groups() -> None:
    services = extrapolate_services(["%prod", "%staging"])
    assert {True, False} == {
        service.has_static_files for service in services if isinstance(service, ToolchainGunicornService)
    }
    assert [svc.service_name for svc in services] == [
        "buildsense/api",
        "buildsense/workflow",
        "payments/api",
        "payments/workflow",
        "scm-integration/api",
        "scm-integration/workflow",
        "servicerouter",
        "toolshed",
        "users/api",
        "users/ui",
        "users/workflow",
        "webhooks",
    ]


@pytest.mark.parametrize(
    "service_specs", [["%prod", "pants-demos/depgraph/web"], ["pants-demos/depgraph/web", "%prod"]]
)
def test_extrapolate_group_with_name(service_specs):
    services = extrapolate_services(service_specs)
    assert {True, False} == {
        service.has_static_files for service in services if isinstance(service, ToolchainGunicornService)
    }
    assert [svc.service_name for svc in services] == [
        "buildsense/api",
        "pants-demos/depgraph/web",
        "payments/api",
        "scm-integration/api",
        "servicerouter",
        "toolshed",
        "users/api",
        "users/ui",
        "webhooks",
    ]


def test_service_dir_override() -> None:
    assert get_service("proxy-server").service_dir == Path("remoting")

    # Ensure every other service not using a `service_dir` override has the correct service_dir.
    for service in extrapolate_services(["%prod"]):
        if service.service_name in ("buildgrid", "proxy-server"):
            continue
        assert service.service_dir == Path(service.service_name.replace("-", "_"))


def test_extrapolate_remoting_proxy() -> None:
    svc = get_service("proxy-server")
    assert isinstance(svc, ToolchainRustService)
    assert svc.ecr_repo_name == "remoting/proxy_server"
    assert svc.binary_name == "proxy_server"
    assert svc.docker_path == "remoting/proxy-server"


def test_extrapolate_remoting_storage_server() -> None:
    svc = get_service("storage-server")
    assert isinstance(svc, ToolchainRustService)
    assert svc.ecr_repo_name == "remoting/storage_server"
    assert svc.binary_name == "storage_server"
    assert svc.docker_path == "remoting/storage-server"


def test_ports_overlap() -> None:
    services = [svc for svc in get_service_config()["services"] if "dev_port" in svc]
    ports = {svc["dev_port"] for svc in services}
    assert len(services) == len(ports), "Duplicate port numbers in services.json"
