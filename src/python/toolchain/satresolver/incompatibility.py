# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from collections.abc import Iterable

from toolchain.satresolver.cause import Cause, ConflictCause, DependencyCause, RootCause
from toolchain.satresolver.term import RootConstraint, Term, VersionConstraint


class Incompatibility:
    """A set of mutually-incompatible terms.

    Incompatibilities are statements of fact that are tested against the state of the current solution.

    A two term incompatibility can be read as:
      "If the current solution satisfies either of these terms, then the other term is incompatible."
    ex:
      The statement "Package foo:1.0.0 depends on package bar:2.0.0" can be represented by the incompatibility:
      Incompatibility(
        terms = [
          VersionConstraint(package_name='foo', versions={foo:1.0.0}, is_positive=True),
          VersionConstraint(package_name='bar', versions={bar:2.0.0}, is_positive=False)],
        cause = DependencyCause(),
      )
    which can be read as:
      "Because foo:1.0.0 depends on bar:2.0.0, foo:1.0.0 is incompatible with not bar:2.0.0."

    A single term incompatibility can be read as:
      "Regardless of the current state of the solution, Term is incompatible."
    Thus the incompatibility:
      Incompatibility(
        terms=[RootConstraint(is_positive=False))],
        cause=RootCause(),
      )
    represents the notion that any solution which does not include __ROOT__ is invalid.
    """

    def __init__(self, terms: Iterable[Term], cause: Cause):
        self.terms = list(terms)
        self.cause = cause

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.cause}, {self.terms})"

    def _is_equal(self, other) -> bool:
        if not isinstance(other, Incompatibility):
            return NotImplemented
        return (self.terms, self.cause) == (other.terms, other.cause)

    def __eq__(self, other) -> bool:
        return self._is_equal(other)

    def __ne__(self, other) -> bool:
        return not self._is_equal(other)

    def __str__(self):
        if isinstance(self.cause, DependencyCause):
            return self._dependency_string()
        if isinstance(self.cause, (ConflictCause, RootCause)):
            if len(self.terms) < 2:
                return f"{self.terms[0]} is incompatible"
            return f"{self.terms[0]} is incompatible with {self.terms[1]}"
        return self.__repr__()

    def __hash__(self):
        return hash(self.__repr__())

    def _dependency_string(self) -> str:
        if isinstance(self.terms[0], VersionConstraint) and self.terms[0].versions == self.terms[0]._all_versions:
            dependee_string = f"all versions of {self.terms[0].subject} depend on"
        else:
            dependee_string = f"{self.terms[0]} depends on"
        if isinstance(self.terms[1], VersionConstraint) and self.terms[1].versions == self.terms[1]._all_versions:
            dependency_string = str(self.terms[1].subject)
        else:
            dependency_string = str(self.terms[1].inverse())
        return f"{dependee_string} {dependency_string}"

    @property
    def is_failure(self) -> bool:
        """Returns True if this incompatibility indicates that version solving has failed."""
        if len(self.terms) == 0 or (len(self.terms) == 1 and isinstance(self.terms[0], RootConstraint)):
            return True
        return False
