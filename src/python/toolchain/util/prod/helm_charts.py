# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from collections.abc import Hashable
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from packaging import version
from ruamel.yaml import YAML
from ruamel.yaml.representer import RoundTripRepresenter, SafeRepresenter

from toolchain.base.frozendict import FrozenDict
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.config.services import ToolchainService

_logger = logging.getLogger(__name__)

# RoundTripRepresenter.represent_none can choose to represent None values as empty strings when dumping dicts.
# We don't that behavior, so we force ruamel.yaml to use SafeRepresenter.represent_none which will dump None values as `null`.
RoundTripRepresenter.add_representer(type(None), SafeRepresenter.represent_none)


@dataclass(frozen=True)
class ServiceChartInfo:
    service_name: str
    chart_name: str
    chart_path: Path
    service_config: FrozenDict[str, Hashable]

    @classmethod
    def for_service(cls, service: ToolchainService):
        """Calculate the chart name and the path to Chart.yaml.

        The chart name is a shorthand name we use for the release name and package name.   E.g., infosite,
        buildsense/api, servicerouter, buildsense/workflow. The chart path is the path to the parent of the Chart.yaml
        file relative to the repo root.  E.g., prod/helm/infosite/infosite, prod/helm/buildsense/api/buildsense-api.
        """
        chart_path = Path("prod") / "helm" / service.chart_path
        return cls(
            service_name=service.service_name,
            chart_name=service.name,
            chart_path=chart_path,
            service_config=service.service_config,
        )

    def get_values(self) -> dict:
        return HelmChart.get_chart_values(self.chart_path)


@dataclass(frozen=True)
class RemoteHelmChart:
    name: str
    version: str


@dataclass(frozen=True)
class HelmChart:
    CHART_YAML = "Chart.yaml"
    VALUES_YAML = "values.yaml"

    path: Path

    @classmethod
    def get_chart_values(cls, chart_path: Path) -> dict:
        return cls.for_path(chart_path).get_values()

    @classmethod
    def for_path(cls, chart_path: Path) -> HelmChart:
        if not chart_path.exists() or not chart_path.is_dir():
            raise ToolchainAssertion(f"Invalid helm chart path: {chart_path}")
        return cls(chart_path)

    def _load_chart_yaml(self, file_name: str, with_roundtrip: bool) -> dict:
        raw_data = (self.path / file_name).read_bytes()
        yaml_helper = YAML(typ="rt" if with_roundtrip else "unsafe", pure=True)
        return yaml_helper.load(raw_data)

    @cached_property
    def name(self) -> str:
        chart_yaml = self.get_chart_manifest()
        return chart_yaml["name"]

    @cached_property
    def version(self) -> str:
        chart_yaml = self.get_chart_manifest()
        return chart_yaml["version"]

    @property
    def manifest_path(self) -> Path:
        return self.path / self.CHART_YAML

    def get_chart_manifest(self, with_roundtrip: bool = False) -> dict:
        return self._load_chart_yaml(self.CHART_YAML, with_roundtrip=with_roundtrip)

    def increment_chart_version(self):
        curr_ver = version.parse(self.version)
        chart_version = list(curr_ver.release)
        chart_version[1] = chart_version[1] + 1
        chart_version[2] = 0
        new_ver = ".".join(str(part) for part in chart_version)
        _logger.info(f"{self.path} {curr_ver} -> {new_ver}")
        self.update_chart_version(new_ver)

    def update_chart_version(self, new_version: str) -> None:
        manifest = self.get_chart_manifest(with_roundtrip=True)
        manifest["version"] = new_version
        self.save_chart_manifest(manifest)

    def save_chart_manifest(self, manifest: dict) -> None:
        yaml_helper = YAML(typ="rt")
        with self.manifest_path.open(mode="w") as fp:
            yaml_helper.dump(manifest, stream=fp)

    def get_values(self, with_roundtrip: bool = False) -> dict:
        return self._load_chart_yaml(self.VALUES_YAML, with_roundtrip=with_roundtrip)

    def save_values(self, values: dict) -> None:
        values_path = self.path / self.VALUES_YAML
        yaml_helper = YAML(typ="rt")
        with values_path.open(mode="w") as fp:
            yaml_helper.dump(values, stream=fp)

    @property
    def has_depednencies(self) -> bool:
        return bool(self.get_chart_manifest().get("dependencies"))


def get_item_by_name(data: list[dict], name: str):
    for item in data:
        if item["name"] == name:
            return item
    raise ToolchainAssertion(f"{name} not found.")
