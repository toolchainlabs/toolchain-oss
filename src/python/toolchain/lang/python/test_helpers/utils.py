# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from typing import ContextManager

import pkg_resources

from toolchain.util.test.util import extract_testbin_file


def load_fixture(fixture_name: str) -> str:
    return pkg_resources.resource_string(__name__, f"testdata/{fixture_name}").decode()


def extract_distribution(distribution_name: str) -> ContextManager[str]:
    return extract_testbin_file(__name__, f"testdata/{distribution_name}.testbin")


def get_dist_binary_data(distribution_name: str) -> bytes:
    with extract_distribution(distribution_name) as dist_path, open(dist_path, "rb") as dist_file:
        return dist_file.read()
