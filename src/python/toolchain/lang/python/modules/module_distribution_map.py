# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from collections.abc import Iterable

from pkg_resources import Distribution

from toolchain.lang.python.distributions.distribution_key import canonical_project_name
from toolchain.util.leveldb.dataset import Dataset


class ModuleDistributionMap(Dataset):
    """Code to query a module -> distributions leveldb."""

    def get_distributions_for_modules(self, modules: list[str]) -> dict[str, list[Distribution]]:
        return {module: list(self.get_distributions_for_module(module)) for module in modules}

    def get_distributions_for_module(self, module: str) -> Iterable[Distribution]:
        value: bytes = self._db.get(module.encode())
        if not value:
            return
        versions_bytes = value.split(b"\0")
        for version_bytes in versions_bytes:
            version_strs = version_bytes.decode().split("\t")
            project_name = canonical_project_name(version_strs[0])
            versions = version_strs[1:]
            for version in versions:
                yield Distribution(project_name=project_name, version=version)
