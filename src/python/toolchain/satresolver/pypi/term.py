# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache

from toolchain.satresolver.pypi.platforms import Platform
from toolchain.satresolver.pypi.python_interpreter import PythonInterpreter
from toolchain.satresolver.term import Term, VersionConstraint

# TODO: a package that requires python may be satisfied with a Cpython/Jython/etc interpreter.
# The inverse is not true.


class PythonInterpreterConstraint(VersionConstraint):
    """A statement about an interpreter which is true or false for a given set of interpreters and interpreter
    versions."""

    def __init__(self, versions: Iterable[PythonInterpreter], is_positive: bool, all_versions: set):
        super().__init__("", versions, is_positive, all_versions)

    def _is_equal(self, other) -> bool:
        return (
            isinstance(other, PythonInterpreterConstraint)
            and self.versions == other.versions
            and self.is_positive == other.is_positive
        )

    def __eq__(self, other) -> bool:
        return self._is_equal(other)

    def __ne__(self, other) -> bool:
        return not self._is_equal(other)

    def __lt__(self, other):
        if isinstance(other, PythonInterpreterConstraint):
            return (self.is_positive, sorted(self.versions)) < (other.is_positive, sorted(other.versions))
        if isinstance(other, Term):
            return self.subject < other.subject
        raise TypeError(f"Can't compare {self} with {other}")

    def __hash__(self):
        return hash((self.versions, self.is_positive))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.versions}, {self.is_positive})"

    def __str__(self) -> str:
        _not = "" if self.is_positive else "not "
        return f"{_not}{self._version_string}"

    @property
    def subject(self) -> str:
        return PythonInterpreter.__name__

    @property
    def allowed_versions(self) -> frozenset[str]:
        if self.is_positive:
            return frozenset(self._all_versions.intersection(self.versions))
        else:
            return frozenset(self._all_versions - self.versions)

    @property
    def _version_string(self) -> str:
        if self.versions == self._all_versions:
            return f"{self.subject}:Any"
        versions = ", ".join([str(version) for version in sorted(self.versions)])
        if len(self.versions) > 1:
            versions = f"({versions})"
        return versions

    def _satisfies(self, other) -> bool:
        if not self.is_positive and other.is_positive:
            return False
        return self.allowed_versions.issubset(other.allowed_versions)

    def inverse(self) -> PythonInterpreterConstraint:
        return PythonInterpreterConstraint(
            versions=self.versions, is_positive=not self.is_positive, all_versions=self._all_versions
        )

    def _intersect(self, other) -> PythonInterpreterConstraint | None:
        if not self.is_positive and not other.is_positive:
            versions = frozenset(self.versions.union(other.versions))
            is_positive = False
        else:
            versions = frozenset(self.allowed_versions.intersection(other.allowed_versions))
            is_positive = True
        if not versions:
            return None
        return PythonInterpreterConstraint(versions=versions, is_positive=is_positive, all_versions=self._all_versions)

    def _difference(self, other) -> PythonInterpreterConstraint | None:
        versions = self.allowed_versions - other.allowed_versions
        if not versions:
            return None
        return PythonInterpreterConstraint(versions=versions, is_positive=True, all_versions=self._all_versions)


class PlatformConstraint(VersionConstraint):
    def __init__(self, platform, versions, all_versions, is_positive):
        super().__init__("", versions, is_positive, all_versions)
        self.platform = platform

    def __hash__(self):
        return hash((self.platform, self.versions, self._is_positive))

    def __repr__(self):
        return f"PlatformConstraint(platform={self.platform}, is_positive={self.is_positive}"

    def __str__(self):
        return f'{"" if self.is_positive else "not "}{self.platform}'

    def __eq__(self, other):
        if not isinstance(other, PlatformConstraint):
            return NotImplemented
        return (
            self.platform == other.platform
            and self.versions == other.versions
            and self.is_positive == other.is_positive
        )

    def __lt__(self, other):
        if isinstance(other, PlatformConstraint):
            return (self.platform, self.is_positive) < (other.platform, other.is_positive)
        if isinstance(other, Term):
            return self.subject < other.subject
        return NotImplemented

    @property
    def subject(self):
        """This is used as the key for grouping all related terms."""
        return Platform.__name__

    def _satisfies(self, other) -> bool:
        if not isinstance(other, PlatformConstraint):
            return NotImplemented
        if not self.is_positive and other.is_positive:
            return False
        return self.allowed_versions.issubset(other.allowed_versions)

    @lru_cache(maxsize=None)
    def _cached_intersect(self, other):
        # Wrapper to get around mypy type checking error
        if not self.is_positive and not other.is_positive:
            # In the case of two negative terms we must return a negative term otherwise we introduce a requirement
            # where previously there was only a filter.
            # The intersection of `not foo:a` and `not foo:b` is `not (foo:a or foo:b)`, rather than `foo:c`
            versions = self.versions.union(other.versions)
            is_positive = False
        else:
            versions = self.allowed_versions.intersection(other.allowed_versions)
            is_positive = True
        if not versions:
            return None
        return PlatformConstraint(
            platform=self.platform, versions=versions, is_positive=is_positive, all_versions=self._all_versions
        )

    def _intersect(self, other) -> PlatformConstraint | None:
        return self._cached_intersect(other)

    def inverse(self) -> PlatformConstraint:
        """Return a new Term representing the inverse of this one."""
        return PlatformConstraint(
            platform=self.platform,
            versions=self.versions,
            all_versions=self._all_versions,
            is_positive=not self.is_positive,
        )

    def _difference(self, other) -> PlatformConstraint | None:
        versions = self.allowed_versions - other.allowed_versions
        if not versions:
            return None
        return PlatformConstraint(
            platform=self.platform, versions=versions, is_positive=True, all_versions=self._all_versions
        )
