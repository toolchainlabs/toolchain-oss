# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from dataclasses import dataclass
from functools import total_ordering

from packaging.version import InvalidVersion, Version

from toolchain.lang.python.distributions.distribution_key import DistributionKey

_DEFAULT_VERSION = Version("0.0.0")


def _parse_version(version: str) -> Version:
    try:
        return Version(version)
    except InvalidVersion:
        return _DEFAULT_VERSION


@dataclass(frozen=True)
class ResolutionData:
    """Resolution-related data for a python package distribution."""

    requires: tuple[str, ...]
    sha256: bytes

    @classmethod
    def create(cls, *, requirements: tuple[str, ...], sha256_hexdigest: str) -> ResolutionData:
        """Create an instance from fields and metadata extracted from a distribution."""
        return ResolutionData(requires=requirements, sha256=bytes.fromhex(sha256_hexdigest))

    def to_bytes(self) -> bytes:
        # \t is not a valid character in any field, so we can use it to delimit the tuple members in requires.
        # The format is (<sha256><requirement1>\t<requirement2>\t...\t<requirementn>).
        # The sha256 field is always exactly 32 bytes, so we can always decode this.
        return self.sha256 + "\t".join(self.requires).encode()

    @classmethod
    def from_bytes(cls, buf: bytes) -> ResolutionData:
        requires = tuple() if len(buf) == 32 else tuple(buf[32:].decode().split("\t"))
        return cls(requires, buf[0:32])


@total_ordering
@dataclass(frozen=True)
class PythonPackageDistribution:
    """A structure representing a specific python package distribution participating in a resolve."""

    key: DistributionKey
    value: ResolutionData

    @classmethod
    def create(cls, key: DistributionKey, value: ResolutionData) -> PythonPackageDistribution:
        return cls(key=key, value=value)

    @property
    def subject(self) -> str:
        return self.package_name

    @property
    def _version(self) -> Version:
        return _parse_version(self.key.version)

    @property
    def sha256_hexdigest(self) -> str:
        return self.sha256.hex()

    @property
    def sha256(self) -> bytes:
        return self.value.sha256

    @property
    def requires(self) -> tuple[str, ...]:
        return self.value.requires

    @property
    def package_name(self) -> str:
        return self.key.package_name

    @property
    def version(self) -> str:
        return self.key.version

    @property
    def requires_python(self) -> str:
        return self.key.requires_python

    @property
    def platform(self) -> str:
        return self.key.platform

    @property
    def abi(self) -> str:
        return self.key.abi

    def __lt__(self, other):
        if not isinstance(self, type(other)):
            return NotImplemented
        return (self.package_name, self._version, self.key) < (other.package_name, other._version, other.key)

    def __str__(self) -> str:
        return f"{self.package_name} {self.version}"
