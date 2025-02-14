# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import zipfile
from pathlib import PurePosixPath

from toolchain.lang.python.distributions.distribution_type import DistributionType
from toolchain.lang.python.distributions.sdist_reader import SDistReader
from toolchain.lang.python.util import module_for_file, read_top_level_txt


def get_modules_for_dist(distribution_type: DistributionType, path: str) -> set[str]:
    raw_modules = get_raw_modules_for_dist(distribution_type, path)
    return {name for name in raw_modules if _is_valid_module(name)}


def _is_valid_module(name: str) -> bool:
    # We can add more checks in the future, for now it is just a simple unicode check to work around a specific issue.
    try:
        name.encode()
    except UnicodeEncodeError:
        return False
    return True


def get_raw_modules_for_dist(distribution_type: DistributionType, path: str) -> set[str]:
    if distribution_type == DistributionType.SDIST:
        return SDistReader.open_sdist(path).get_exported_modules()
    # bdists and wheels are zipfiles containing .py and .so files packaged relative to the root.
    with zipfile.ZipFile(path) as zpf:
        names = sorted(PurePosixPath(name) for name in zpf.namelist())
        declared_top_level_modules = read_top_level_txt(names, lambda name: zpf.read(str(name)))
    modules: set[str] = set(declared_top_level_modules or [])
    for name in names:
        for module in module_for_file(name, exportable_only=True):
            if module not in modules:
                if declared_top_level_modules:
                    # We have declared_top_level_modules, so filter by them.
                    for top_level_module in declared_top_level_modules:
                        if module.startswith(f"{top_level_module}."):
                            modules.add(module)
                else:
                    # Otherwise, take all modules we find.
                    modules.add(module)
    return modules
