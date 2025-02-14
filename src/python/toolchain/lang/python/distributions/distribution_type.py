# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from enum import Enum, unique

import pkginfo

from toolchain.base.toolchain_error import ToolchainAssertion


class UnsupportedDistributionType(ToolchainAssertion):
    pass


@unique
class DistributionType(Enum):
    WHEEL = "WHEEL"
    BDIST = "BDIST"
    SDIST = "SDIST"
    EXE = "EXE"
    RPM = "RPM"
    DUMB = "DUMB"
    MSI = "MSI"

    @classmethod
    def from_setuptools_packagetype(cls, packagetype: str) -> DistributionType:
        """Convert a setuptools `packagetype` value to DistributionType."""
        dist_type = _DIST_MAP.get(packagetype)
        if not dist_type:
            raise UnsupportedDistributionType(f"Unsupported packagetype: {packagetype}")
        return dist_type

    @classmethod
    def from_pkginfo_distribution(cls, dist: pkginfo.Distribution) -> DistributionType:
        if isinstance(dist, pkginfo.Wheel):
            return cls.WHEEL
        if isinstance(dist, pkginfo.BDist):
            return cls.BDIST
        if isinstance(dist, pkginfo.SDist):
            return cls.SDIST
        raise UnsupportedDistributionType(f"Unsupported Distribution subclass: {type(dist)}")

    @classmethod
    def django_model_field_choices(cls):
        return ((x.value, x.value) for x in cls)


_DIST_MAP = {
    "bdist_wheel": DistributionType.WHEEL,
    "bdist_egg": DistributionType.BDIST,
    "bdist_wininst": DistributionType.EXE,
    "bdist_rpm": DistributionType.RPM,
    "bdist_dumb": DistributionType.DUMB,
    "bdist_msi": DistributionType.MSI,
    "sdist": DistributionType.SDIST,
}
