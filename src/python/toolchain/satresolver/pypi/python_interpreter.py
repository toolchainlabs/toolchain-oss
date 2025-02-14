# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from dataclasses import dataclass
from functools import total_ordering


@total_ordering
@dataclass(frozen=True, order=False)
class PythonInterpreter:
    """A specific python interpreter.

    `interpreter` may be Python, Cpython, Ironpython, Jython etc, but they all must have the same subject as they
    compete with one another. A resolve that includes both Python and Cpython interpreters would be invalid.
    """

    interpreter: str
    version: str

    @property
    def subject(self) -> str:
        return self.__class__.__name__

    def __lt__(self, other):
        try:
            return (self.subject, self.version) < (other.subject, other.version)
        except AttributeError:
            return NotImplemented
