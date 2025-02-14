# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from abc import ABCMeta, abstractmethod
from collections import defaultdict
from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.config.services import (
    BuildResult,
    ServiceBuildResult,
    ServicesBuildResults,
    ServiceType,
    ToolchainGunicornService,
    ToolchainRustService,
    ToolchainService,
    ToolchainWorkflowService,
)
from toolchain.prod.builders.build_gunicorn import GunicornAppBuilder
from toolchain.prod.builders.build_rust_services import RustServiceBuilders
from toolchain.prod.builders.build_workflow import WorkflowServiceBuilder

B = TypeVar("B", bound="ImageBuilder")
S = TypeVar("S", bound="ToolchainService")


class ImageBuilder(Generic[S], metaclass=ABCMeta):
    """A service docker image builder."""

    class ConfigurationError(ToolchainAssertion):
        """Indicates an error in the json configuration for an ImageBuilder."""

    class MissingKeyError(ConfigurationError):
        """Indicates a missing configuration key."""

    class ValueTypeError(ConfigurationError):
        """Indicates a configuration value having the wrong type."""

    V = TypeVar("V")

    @classmethod
    def require(cls, obj: dict[str, Any], key: str, expected_type: type[ImageBuilder.V]) -> ImageBuilder.V:
        """Extracts a required value of the given type from a JSON object.

        NB: The corresponding JSON object entry is removed from the JSON object if found.
        """
        if key not in obj:
            raise cls.MissingKeyError(
                f"The {key!r} is required to configure {cls.__name__}, given configuration: {obj}."
            )
        value = obj.pop(key)
        if not isinstance(value, expected_type):
            raise cls.ValueTypeError(
                f"Expected {key!r} to be of type {expected_type.__name__}, "
                f"got {value} of type {type(value).__name__}."
            )
        return value

    @classmethod
    def from_json(cls: type[B], obj: dict[str, Any]) -> B:
        """Convert a JSON configuration object into an ImageBuilder of this type.

        NB: The JSON object is copy that can be safely mutated.
        """
        if obj:
            raise cls.ConfigurationError(f"Unexpected configuration for {cls.__name__}: {obj}")
        return cls()

    @property
    @abstractmethod
    def chart_parameters(self) -> tuple[str, ...]:
        """The Helm chart parameter name for the image version produced by `build_services`."""

    @abstractmethod
    def build_services(
        self, services: Sequence[S], *, env_name: str | None = None, max_workers: int | None = None, push: bool = True
    ) -> BuildResult:
        """Build the docker images for all the given services and return the common image version.

        :param services: The services to build a docker image for.
        :param env_name: The environment for which we are building the service for (dev, prod)
        :param max_workers: The maximum number of workers to use for building docker images at once.
        """


class GunicornBuilder(ImageBuilder[ToolchainGunicornService]):
    @property
    def chart_parameters(self) -> tuple[str, ...]:
        return ("gunicorn_image_rev",)

    def build_services(
        self,
        services: Sequence[ToolchainGunicornService],
        *,
        env_name: str | None = None,
        max_workers: int | None = None,
        push: bool = True,
    ) -> BuildResult:
        gunicorn_app_builder = GunicornAppBuilder(env_name, max_workers=max_workers, push=push)
        return gunicorn_app_builder.build_services(services)


class WorkflowBuilder(ImageBuilder[ToolchainWorkflowService]):
    @property
    def chart_parameters(self) -> tuple[str, ...]:
        return ("workflow_server_rev", "workflow_maintenance_image_rev")

    def build_services(
        self,
        services: Sequence[ToolchainWorkflowService],
        *,
        env_name: str | None = None,
        max_workers: int | None = None,
        push: bool = True,
    ) -> BuildResult:
        workflow_builder = WorkflowServiceBuilder(env_name, max_workers=max_workers, push=push)
        return workflow_builder.build_services(services)


class RustBuilder(ImageBuilder[ToolchainRustService]):
    @property
    def chart_parameters(self) -> tuple[str, ...]:
        return ("image_rev",)

    def build_services(
        self,
        services: Sequence[ToolchainRustService],
        *,
        env_name: str | None = None,
        max_workers: int | None = None,
        push: bool = True,
    ) -> BuildResult:
        builder = RustServiceBuilders(environment_name=env_name, push=push)
        return builder.build_services(services)


_BUILDER_TYPES = {
    ServiceType.GUNICORN: GunicornBuilder,
    ServiceType.WORKFLOW: WorkflowBuilder,
    ServiceType.RUST: RustBuilder,
}


class InvalidBuildConfigError(ToolchainAssertion):
    """Indicates an invalid service build configuration in `services.json`."""


def for_service(service: S) -> ImageBuilder[S]:
    builder_class = _BUILDER_TYPES.get(service.service_type)
    if not builder_class:
        raise InvalidBuildConfigError(f"No builder associated with {service.service_name}.")
    return builder_class()  # type: ignore[abstract,return-value]


def _get_builders_for_services(
    services: Sequence[ToolchainService],
) -> list[tuple[ImageBuilder, list[ToolchainService]]]:
    if not services:
        raise ToolchainAssertion("Empty services sequence")
    service_types: dict[type, list[ToolchainService]] = defaultdict(list)
    for service in services:
        service_types[type(service)].append(service)
    return [(for_service(services[0]), services) for services in service_types.values()]


def build_services(
    services: Sequence[ToolchainService],
    env_name: str | None,
    max_workers: int,
    push: bool = True,
) -> ServicesBuildResults:
    results: list[ServiceBuildResult] = []
    for builder, services_for_builder in _get_builders_for_services(services):
        result = builder.build_services(services_for_builder, env_name=env_name, max_workers=max_workers, push=push)
        # TODO: build_services should eventually return this list.
        results.extend(
            ServiceBuildResult(
                service=service,
                chart_parameters=builder.chart_parameters,
                revision=result.revision,
                commit_sha=result.commit_sha,
                output=result.output,
            )
            for service in services_for_builder
        )
    return tuple(results)
