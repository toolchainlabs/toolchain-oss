# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import itertools
from collections import OrderedDict
from collections.abc import Iterator

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.lang.python.distributions.distribution_key import DistributionKey, canonical_project_name
from toolchain.satresolver.pypi.python_distribution import PythonPackageDistribution, ResolutionData
from toolchain.util.leveldb.dataset import Dataset


class Depgraph(Dataset):
    """Code to query a PyPI depgraph leveldb table."""

    def get_distributions(
        self,
        package_name: str,
        version: str | None = None,
        distribution_type: str | None = None,
        requires_python: str | None = None,
        platform: str | None = None,
        abi: str | None = None,
        build: str | None = None,
    ) -> Iterator[PythonPackageDistribution]:
        """Returns all distributions matching the given args.

        Any omitted args are treated as wildcards, matching any value.
        """
        # Works in two stages:
        # 1. Uses the longest key prefix fixed by the args to scan as small a range as possible of the table.
        # 2. Filters the resulting keys against the other non-None args.

        # Make sure the scan doesn't iterate over the entire table.
        if package_name is None:
            raise ToolchainAssertion("No package_name specified.")

        package_name = canonical_project_name(package_name)

        # Find the longest prefix of non-None key components.
        fixed_key_prefix_components, filter_kwargs = self.compute_prefix_and_filter(
            package_name=package_name,
            version=version,
            distribution_type=distribution_type,
            requires_python=requires_python,
            platform=platform,
            abi=abi,
            build=build,
        )

        prefix = ("\t".join(fixed_key_prefix_components) + "\t").encode()
        # Scan over the range and filter each key.
        for key_bytes, value_bytes in self.db.iterator(prefix=prefix):
            key = DistributionKey.from_ordered_bytes(key_bytes)
            if self.filter_key(key, **filter_kwargs):
                # TODO: make sure all PythonPackageDistribution() for a given distribution are unique (no duplicates)
                # We used to to that by creating a set over the PythonPackageDistribution objects, but this should be done when creating the
                # level db entries.
                yield PythonPackageDistribution.create(key, ResolutionData.from_bytes(value_bytes))

    @staticmethod
    def compute_prefix_and_filter(
        package_name,
        version=None,
        distribution_type=None,
        requires_python=None,
        platform: str | None = None,
        abi: str | None = None,
        build: str | None = None,
    ) -> tuple[list[str], dict]:
        """Compute the fixed key prefix and subsequent non-None filter kwargs for the given args."""

        # Note that (in Py3.6+) OrderedDict preserves its constructor kwargs order.
        kwargs = OrderedDict(
            package_name=package_name,
            version=version,
            distribution_type=distribution_type,
            requires_python=requires_python,
            platform=platform,
            abi=abi,
            build=build,
        )

        # Find the longest prefix of non-None key components.
        fixed_key_prefix_components = list(itertools.takewhile(lambda x: x is not None, kwargs.values()))

        # The filter kwargs are the remaining non-None components.
        filter_kwargs = {k: v for k, v in list(kwargs.items())[len(fixed_key_prefix_components) :] if v is not None}

        return fixed_key_prefix_components, filter_kwargs

    @staticmethod
    def filter_key(key: DistributionKey, **kwargs) -> bool:
        """Filter the key on any restrictions not in the prefix (and therefore not used to restrict the scan range).

        Returns True iff the key matches the (non-None) field values specified in the kwargs.
        """
        for kwarg_name, kwarg_value in kwargs.items():
            if kwarg_value is not None and getattr(key, kwarg_name) != kwarg_value:
                return False
        return True
