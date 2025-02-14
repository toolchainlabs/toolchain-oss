# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from pathlib import Path
from types import GeneratorType

from toolchain.lang.python.modules.module_distribution_map import ModuleDistributionMap
from toolchain.util.leveldb.test_helpers.utils import write_level_db

MODULES_MAP_1 = {
    "jerry.soup": {"tinsel": {"1.0.0", "1.1.0", "12.23.91"}, "festivus": {"0.88.dev32", "1.1.0", "12.23.91"}},
    "pole": {"izzy": {"1.2.3a", "14.4.0", "10.10.223"}, "superman": {"1.12.0"}},
}


MODULES_MAP_2 = {
    "keith": {"coffee": {"12.23.91", "2.0.33"}},
    "junior": {"nypl": {"81.0.22", "6.2.0dev33"}},
    "bookman": {"library": {"0.2.882", "3.24.0"}, "joke": {"1.8.0"}},
    "joyboy": {"oneweek": {"772.0", "2019.3.11"}, "older": {"77.0.22dev88"}},
}


def create_fake_modules_map(tmp_path: Path, modules_map: dict[str, dict[str, set[str]]]) -> ModuleDistributionMap:
    def _join_vers(versions: set[str]) -> str:
        return "\t".join(sorted(versions))

    def _serialize(package_to_versions: dict[str, set[str]]) -> bytes:
        versions = (
            f"{package_name}\t{_join_vers(versions)}".encode()
            for package_name, versions in sorted(package_to_versions.items())
        )
        return b"\0".join(versions)

    items = ((module.encode(), _serialize(package_to_versions)) for module, package_to_versions in modules_map.items())
    write_level_db(tmp_path, items)
    return ModuleDistributionMap.from_path(tmp_path.as_posix())


def test_get_distributions_for_module(tmp_path: Path) -> None:
    modules_map = create_fake_modules_map(tmp_path, MODULES_MAP_1)
    dist_iter = modules_map.get_distributions_for_module("jerry.soup")
    assert isinstance(dist_iter, GeneratorType)
    distributions = list(dist_iter)
    assert len(distributions) == 6
    assert distributions[0].project_name == "festivus"
    assert distributions[0].version == "0.88.dev32"
    assert distributions[3].project_name == "tinsel"
    assert distributions[3].version == "1.0.0"
