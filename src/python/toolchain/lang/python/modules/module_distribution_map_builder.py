# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from collections import defaultdict

from toolchain.lang.python.distributions.distribution_data_builder import DistributionDataBuilder
from toolchain.lang.python.distributions.distribution_key import DistributionKey

logger = logging.getLogger(__name__)


class DistributionModuleMapBuilder(DistributionDataBuilder):
    """Builds a leveldb map from module name to list of distributions providing that module."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # A map from module -> (package name -> version set).
        # We accumulate data here before flushing it at the end of the batch. The initialization function
        # adds any data from previous batches, so that we add to that in the new batch instead of overwriting it.
        self._module_map: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        self._reset_for_new_batch()

    def _reset_for_new_batch(self) -> None:
        self._module_map.clear()

    def process_row(
        self,
        key: DistributionKey,
        sha256_hexdigest: str,
        requires: list[str],
        requires_dist: list[str],
        modules: list[str],
    ) -> None:
        for module in modules:
            package_name_to_versions = self._get_initialized_data(module)
            package_name_to_versions[key.package_name].add(key.version)
            self.item_handled()

    def flush(self) -> None:
        for module, package_name_to_version in self._module_map.items():
            versions_bytes = []
            for package_name, versions in sorted(package_name_to_version.items()):
                version_str = package_name + "\t" + "\t".join(sorted(versions))
                versions_bytes.append(version_str.encode())
            self.put(module.encode(), b"\0".join(versions_bytes))
        self._reset_for_new_batch()
        super().flush()

    def _get_initialized_data(self, module: str) -> dict[str, set[str]]:
        """Get the package->versions map for the given module.

        Map is initialized with existing data from previous batches, or a preexisting db.
        """
        package_name_to_versions = self._module_map[module]
        if not package_name_to_versions:
            value = self.db.get(module.encode())
            if value:
                versions_bytes = value.split(b"\0")
                for version_bytes in versions_bytes:
                    version_strs = version_bytes.decode().split("\t")
                    package_name_to_versions[version_strs[0]] = set(version_strs[1:])
        return package_name_to_versions
