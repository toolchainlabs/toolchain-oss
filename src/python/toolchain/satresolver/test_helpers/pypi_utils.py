# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json
from collections.abc import Iterable
from pathlib import Path

import pkg_resources

from toolchain.base.hashutil import compute_sha256_hexdigest
from toolchain.satresolver.pypi.depgraph import Depgraph
from toolchain.satresolver.pypi.python_distribution import PythonPackageDistribution, ResolutionData
from toolchain.util.leveldb.test_helpers.utils import write_level_db


def load_fixture(fixture_name: str) -> dict:
    fixture = pkg_resources.resource_string(__name__, f"fixtures/{fixture_name}.json")
    return json.loads(fixture)


def create_fake_depgraph(tmp_path: Path, *distributions: PythonPackageDistribution) -> Depgraph:
    return create_fake_depgraph_for_dists(tmp_path, distributions)


def create_fake_depgraph_for_dists(tmp_path: Path, distributions: Iterable[PythonPackageDistribution]):
    items_iter = ((dist.key.to_ordered_bytes(), dist.value.to_bytes()) for dist in distributions)
    write_level_db(tmp_path, items_iter)
    return Depgraph.from_path(tmp_path.as_posix())


def get_resolution_data(filename: str, *requires: str) -> ResolutionData:
    return ResolutionData.create(sha256_hexdigest=compute_sha256_hexdigest(filename.encode()), requirements=requires)
