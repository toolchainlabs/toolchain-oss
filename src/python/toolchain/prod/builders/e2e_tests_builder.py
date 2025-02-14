# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from toolchain.config.services import ToolchainService
from toolchain.prod.builders.build_pex_wrapper import PexWrapperBuilder

_logger = logging.getLogger(__name__)

ServiceTestImages = dict[str, str]

TestImages = dict[ToolchainService, ServiceTestImages]


@dataclass(frozen=True)
class ServiceTestDefintion:
    target: str
    name: str
    ecr_repo: str | None = None
    docker_path: str | None = None

    @classmethod
    def for_toolchain(cls, rel_target: str, name: str, docker_path: str | None = None):
        return cls(
            target=f"src/python/toolchain/{rel_target}",
            name=name,
            ecr_repo=f"e2e_tests/{name}",
            docker_path=docker_path,
        )

    @classmethod
    def for_python_service(cls, service: str, docker_path: str | None = None):
        return cls.for_toolchain(
            rel_target=f"service/{service}/e2e_tests:{service}_e2e_tests", name=service, docker_path=docker_path
        )


SERVICES_TO_TESTS = {
    "proxy-server": ServiceTestDefintion.for_toolchain("prod/e2e_tests:setup_jwt_keys", name="setup_jwt_keys"),
    "infosite": ServiceTestDefintion.for_python_service("infosite", docker_path="e2e-tests/selenium"),
    "webhooks": ServiceTestDefintion.for_python_service("webhooks"),
}


class End2EndTestBuilder:
    def __init__(self, environment_name: str) -> None:
        self._env = environment_name

    def build_tests(self, services: Sequence[ToolchainService]) -> TestImages:
        tests: TestImages = {}
        for service in services:
            test_images = self._build_service_test(service.service_name)
            if not test_images:
                continue
            tests[service] = test_images
        return tests

    def _build_service_test(self, service_name: str) -> ServiceTestImages:
        test_versions: ServiceTestImages = {}
        test_or_tests = SERVICES_TO_TESTS.get(service_name)
        if not test_or_tests:
            return test_versions
        tests = (test_or_tests,) if isinstance(test_or_tests, ServiceTestDefintion) else test_or_tests
        for test_def in tests:
            builder = PexWrapperBuilder(
                pants_target=test_def.target,
                ecr_repo=test_def.ecr_repo,
                docker_path=test_def.docker_path,
            )
            image_name = builder.build_and_publish(self._env)
            # Hacky way to get the image tag only since the chart already encodes the repo and registry.
            # TODO: make build_and_publish return a dataclass with all of those parts so they caller can choose what to use.
            test_versions[test_def.name] = image_name.partition(":")[-1]
        return test_versions
