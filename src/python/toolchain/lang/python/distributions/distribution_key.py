# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import re
from dataclasses import astuple, dataclass

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.lang.python.distributions.distribution_type import DistributionType


def canonical_project_name(project_name: str) -> str:
    return project_name.lower().replace("_", "-")


@dataclass(frozen=True, order=True)
class DistributionKey:
    """A composite key that uniquely identify a Python distribution."""

    package_name: str
    version: str
    distribution_type: str
    requires_python: str = "python"
    platform: str = "any"
    abi: str = "none"
    build: str = ""  # Breaks ties if two wheels have the same version. See https://www.python.org/dev/peps/pep-0427/.

    @classmethod
    def create(
        cls,
        filename: str,
        project_name: str,
        version: str,
        distribution_type: DistributionType | str,
        requires_python: str,
    ) -> DistributionKey:
        """Create an instance from fields and metadata extracted from a distribution."""
        dist_type_str = (
            distribution_type.value if isinstance(distribution_type, DistributionType) else distribution_type
        )
        if dist_type_str == DistributionType.SDIST.value:
            match_groups: dict[str, str] = {}
        else:
            parsed_filename = parse_filename(filename, distribution_type)
            match_groups = parsed_filename.groupdict() if parsed_filename else {}

        build = match_groups.get("build") or ""
        abi = match_groups.get("abi") or ""
        platform = match_groups.get("platform") or ""

        package_name = canonical_project_name(project_name)

        return cls(
            package_name=package_name,
            version=version,
            distribution_type=dist_type_str,
            requires_python=requires_python or python_requirement_from_tag(match_groups.get("python", "")),
            platform=platform,
            build=build,
            abi=abi,
        )

    def to_ordered_bytes(self) -> bytes:
        """Returns a serialized representation that sorts in the natural order of the keys.

        I.e., to_ordered_bytes(k1) < to_ordered_bytes(k2) iff k1 < k2.

        This is useful as a key in a sorted string table (e.g., leveldb), allowing us to efficiently scan the table for
        any fixed prefix of the field tuple, E.g., (package_name1,), (package_name1, version1), (package_name1,
        version1, distribution_type1).
        """
        # The ordinal of the tab character precedes that of any character we expect to find in any field.
        # We call this primarily in offline processes that generate serving data structures, so performance
        # is not critical.
        return ("\t".join(astuple(self)) + "\t").encode()

    @classmethod
    def from_ordered_bytes(cls, buf: bytes) -> DistributionKey:
        """Returns a Key instance from ordered bytes as created by to_ordered_bytes()."""
        # TODO: This is called when reading from serving data structures, so benchmark and optimize as needed.
        return cls(*buf.decode().split("\t")[0:-1])

    def __str__(self) -> str:
        return f"Distribution: {self.package_name}=={self.version}[{self.distribution_type}]"


# {project name}-{version}-{optional build tag}-{python tag}-{abi tag}-{platform tag}.whl
WHEEL_PATTERN = re.compile(
    r"(?P<name>[^-]+)-(?P<version>[^-]+)(-(?P<build>[^-]+))?-(?P<python>[^-]+)-(?P<abi>[^-]+)-(?P<platform>[^-]+).whl"
)
# {project name}-{optional version}-{optional python tag}-{optional platform tag}.whl
BDIST_PATTERN = re.compile(r"(?P<name>[^-]+)(-(?P<version>[^-]+)(-(?P<python>py[^-]+)(-(?P<platform>.+))?)?)?.egg")


def parse_filename(filename: str, dist_type: DistributionType | str):
    """Wheels and eggs contain metadata in their filenames which can be missing from their Metadata."""
    dist_type_str = dist_type.value if isinstance(dist_type, DistributionType) else dist_type
    if dist_type_str == DistributionType.WHEEL.value:
        return WHEEL_PATTERN.match(filename)
    elif dist_type_str == DistributionType.BDIST.value:
        return BDIST_PATTERN.match(filename)
    else:
        raise ValueError(f"Cannot call parse_filename on file {filename} with dist_type {dist_type}")


def python_requirement_from_tag(tag):
    """Converts a python requirement tag extracted from a filename into a valid python requirement string."""
    if not tag:
        return ""
    parts = tag.split(".")
    versions = []
    for t in parts:
        match = re.match(r"([a-z]+)(\d+)", t)
        if match is None:
            continue
        _, version = match.groups()
        versions.append(".".join(version))
    if len(versions) == 0:
        return ""
    if len(versions) == 1:
        ver = versions[0]
        # `~=` specifiers can not be used with single segment version numbers.
        # https://www.python.org/dev/peps/pep-0440/#compatible-release
        if len(ver) == 1:
            # py2 -> >2, <3
            return f">{ver},<{int(ver)+1}"
        # py36 -> ~=3.6
        return f"~={ver}"
    elif len(versions) > 1:
        max_version = max(versions)
        if max_version[0] in versions:
            # py3 implies >=3,<4, We should use this larger bound when it is specified, even though `3.7` is greater than `3`
            # py2.py3.py37 -> >=2,<4
            max_version = max_version[0]
        if len(max_version) == 1:
            # py2.py3 -> >=2,<4
            return f">={min(versions)},<{int(max_version)+1}"
        # py27.py36 -> >=2.7,<=3.6.
        return f">={min(versions)},<={max_version}"
    raise ToolchainAssertion(f"Unknown python version: {tag}")
