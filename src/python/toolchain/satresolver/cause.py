# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from toolchain.satresolver.incompatibility import Incompatibility


class Cause:
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}"

    def _is_equal(self, other) -> bool:
        return isinstance(other, self.__class__)

    def __eq__(self, other) -> bool:
        return self._is_equal(other)

    def __ne__(self, other) -> bool:
        return not self._is_equal(other)


class RootCause(Cause):
    """An incompatibility representing the requirement that the root package exists."""


class DependencyCause(Cause):
    """An incompatibility representing a package's dependency."""


class UseLatestCause(Cause):
    """An incompatibility representing the user's request that we use the latest version of a given package."""


class UseLockedCause(Cause):
    """An incompatibility representing the user's request that we use the locked version of a given package."""


class NoVersionsCause(Cause):
    """An incompatibility indicating that the package has no versions that match the given constraint."""


class PackageNotFoundCause(Cause):
    """An incompatibility representing a package that couldn't be found."""

    def __init__(self, exception: Exception):
        self.exception = exception

    def __repr__(self):
        return f"{self.__class__.__name__}({self.exception})"

    def __eq__(self, other):
        if not isinstance(other, PackageNotFoundCause):
            return NotImplemented
        return self.exception.message == other.exception.message


class ConflictCause(Cause):
    """An incompatibility was derived from two existing incompatibilities during conflict resolution."""

    def __init__(self, conflict: Incompatibility, other: Incompatibility):
        self.conflict = conflict
        self.other = other

    def __repr__(self):
        return f"{self.__class__.__name__}({self.conflict}, {self.other})"

    def __eq__(self, other):
        if not isinstance(other, ConflictCause):
            return NotImplemented
        return (self.conflict, self.other) == (other.conflict, other.other)


class IncompatibilityCause(Cause):
    """An incompatibility was derived from an existing incompatibility during incompatibility propagation."""

    def __init__(self, incompatibility: Incompatibility):
        self.incompatibility = incompatibility

    def __repr__(self):
        return f"{self.__class__.__name__}({self.incompatibility})"

    def __eq__(self, other):
        if not isinstance(other, IncompatibilityCause):
            return NotImplemented
        return self.incompatibility == other.incompatibility


class OverrideCause(Cause):
    """An incompatibility representing a package's dependency being overridden by a pinned version."""
