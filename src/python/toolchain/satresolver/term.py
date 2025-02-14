# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from functools import lru_cache, total_ordering

from toolchain.satresolver.package import ROOT


@total_ordering
class Term:
    @classmethod
    def require(cls, **kwargs):
        return cls(is_positive=True, **kwargs)

    @classmethod
    def exclude(cls, **kwargs):
        return cls(is_positive=False, **kwargs)

    @property
    def is_positive(self):
        return self._is_positive

    @property
    def subject(self):
        """This is used as the key for grouping all related terms."""
        return NotImplementedError

    def _is_equal(self, other) -> bool:
        return self.subject == other.subject and self.is_positive == other.is_positive

    def __ne__(self, other) -> bool:
        return not self._is_equal(other)

    def __eq__(self, other) -> bool:
        return self._is_equal(other)

    def __lt__(self, other):
        return (self.subject, self.is_positive) < (other.subject, other.is_positive)

    def satisfies(self, other) -> bool:
        """Returns whether this term being true means that other must also be true."""
        if self.subject != other.subject:
            raise ValueError(f"{other} refers to {other.subject}, not {self.subject}.")
        return self._satisfies(other)

    def _satisfies(self, other):
        raise NotImplementedError

    def intersect(self, other) -> Term:
        """Returns a new Term that represents the values allowed by both this term and other.

        If there is no such Term (eg: this term and other are incompatible), returns None.
        """
        if self.subject != other.subject:
            raise ValueError(f"{other} refers to {other.subject}, not {self.subject}.")
        return self._intersect(other)

    def _intersect(self, other):
        raise NotImplementedError

    def inverse(self):
        """Return a new Term representing the inverse of this one."""
        raise NotImplementedError

    def difference(self, other) -> Term:
        """Returns a Term representing the values allowed by self and not by other.

        If there are no values allowed by self and disallowed by other, returns None.
        """
        if self.subject != other.subject:
            raise ValueError(f"{other} refers to {other.subject}, not {self.subject}.")
        return self._difference(other)

    def _difference(self, other):
        raise NotImplementedError


class VersionConstraint(Term):
    """A statement about a package which is true or false for a given set of package versions.

    If `is_positive` is True, a valid solution must include the package at one of the versions referenced.
    - `Term("foo", set(["b", "c"]), True)` is equivalent to the predicate `foo:a or foo:b`

    If `is_positive` is False, a valid solution must not include the package at any of the versions referenced.
    - `Term("foo", set(["a"]), False)` is equivalent to the predicate `not foo:a`
    """

    def __init__(self, package_name, versions, is_positive, all_versions):
        super().__init__()
        self.package_name = package_name
        self.versions = frozenset(versions)
        self._is_positive = is_positive
        self._all_versions = frozenset(all_versions)

    def __eq__(self, other):
        # HACK. Fix this when all the other constraints inherit from Term instead of VersionConstraint.
        try:
            return (
                isinstance(other, VersionConstraint)
                and self.package_name == other.package_name
                and self.versions == other.versions
                and self.is_positive == other.is_positive
                and self._all_versions == other._all_versions
            )
        except AttributeError:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.package_name, self.versions, self.is_positive, self._all_versions))

    def __repr__(self):
        return (
            f"{self.__class__.__name__}({self.package_name}, {self.versions}, {self.is_positive}, {self._all_versions})"
        )

    def __str__(self):
        _not = "" if self.is_positive else "not "
        return f"{_not}{self._version_string}"

    @property
    def _version_string(self):
        if not self.versions:
            return self.subject
        if self.versions == self._all_versions:
            return f"{self.subject}:Any"
        version_string = ", ".join([str(version) for version in sorted(self.versions)])
        if len(self.versions) == 1:
            return version_string
        return f"({version_string})"

    @property
    def allowed_versions(self):
        if self.is_positive:
            return frozenset(self._all_versions.intersection(self.versions))
        else:
            return frozenset(self._all_versions - self.versions)

    @property
    def subject(self) -> str:
        return self.package_name

    @lru_cache(maxsize=None)
    def _cached_satisfies(self, other):
        # Wrapper to get around mypy type checking error:
        # error: Signature of "_satisfies" incompatible with supertype "Term"
        # Mypy thinks the return type of this function is `functools.lru_cache[frozenset]`
        if not self.is_positive and other.is_positive:
            return False
        return self.allowed_versions.issubset(other.allowed_versions)

    def _satisfies(self, other) -> bool:
        # A VersionConstraint satisfies a second VersionConstraint if both VersionConstraints refer to the same package and
        # the set of versions allowed by the first VersionConstraint is a subset of the versions allowed by the second
        # VersionConstraint.
        # A negative VersionConstraint (`not foo: 1.0.0`) cannot satisfy a positive VersionConstraint (`foo: 1.0.2`) as the
        # negative VersionConstraint may be satisfied by a solution which does not include package foo at all.
        return self._cached_satisfies(other)

    def inverse(self) -> VersionConstraint:
        return VersionConstraint(
            package_name=self.package_name,
            versions=self.versions,
            is_positive=not self.is_positive,
            all_versions=self._all_versions,
        )

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
        return VersionConstraint(
            package_name=self.package_name, versions=versions, is_positive=is_positive, all_versions=self._all_versions
        )

    def _intersect(self, other) -> VersionConstraint | None:
        return self._cached_intersect(other)

    def _difference(self, other) -> VersionConstraint | None:
        versions = self.allowed_versions - other.allowed_versions
        if not versions:
            return None
        return VersionConstraint(
            package_name=self.package_name, versions=versions, is_positive=True, all_versions=self._all_versions
        )


class RootConstraint(Term):
    """A statement about the existence of the `root` of the dependency graph."""

    def __init__(self, is_positive=True):
        self.package_name = ROOT.package_name
        self.versions = frozenset([ROOT])
        self._is_positive = is_positive
        self._all_versions = self.versions

    def __str__(self):
        return f"{'' if self.is_positive else 'not '}{self.package_name}"

    @property
    def subject(self) -> str:
        return self.package_name

    def _satisfies(self, other) -> bool:
        return self == other

    def _intersect(self, other) -> RootConstraint | None:
        return self if self == other else None

    def inverse(self) -> RootConstraint:
        return RootConstraint(is_positive=not self.is_positive)

    def _difference(self, other) -> RootConstraint | None:
        return None if self == other else self
