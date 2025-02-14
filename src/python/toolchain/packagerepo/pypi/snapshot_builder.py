# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from collections import defaultdict

from toolchain.lang.python.distributions.distribution_data_builder import DistributionDataBuilder
from toolchain.lang.python.distributions.distribution_key import DistributionKey
from toolchain.util.leveldb.builder_binary import BuilderBinary

logger = logging.getLogger(__name__)


class SnapshotBuilder(DistributionDataBuilder):
    """Builds a leveldb map from package name to list of known versions for that package."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # A map from package name -> version set.
        # We accumulate data here before flushing it at the end of the batch. The initialization function
        # adds any data from previous batches, so that we add to that in the new batch instead of overwriting it.
        self._package_versions: dict[str, set[str]] = defaultdict(set)
        self._reset_for_new_batch()

    def _reset_for_new_batch(self) -> None:
        self._package_versions.clear()

    def process_row(
        self,
        key: DistributionKey,
        sha256_hexdigest: str,
        requires: list[str],
        requires_dist: list[str],
        modules: list[str],
    ) -> None:
        versions = self._get_initialized_data(key.package_name)
        versions.add(key.version)
        self.item_handled()

    def flush(self) -> None:
        for package_name, versions in self._package_versions.items():
            self.put(package_name.encode(), "\t".join(sorted(versions)).encode())
        self._reset_for_new_batch()
        super().flush()

    def _get_initialized_data(self, package_name: str) -> set[str]:
        """Get the known versions list for the given package.

        List is initialized with existing data from previous batches, or a preexisting db.
        """
        versions = self._package_versions[package_name]
        if not versions:
            value = self.db.get(package_name.encode())
            if value:
                versions.update(value.decode().split("\t"))
        return versions


class SnapshotBuilderBinary(BuilderBinary):
    BuilderClass = SnapshotBuilder


if __name__ == "__main__":
    SnapshotBuilderBinary.start()
