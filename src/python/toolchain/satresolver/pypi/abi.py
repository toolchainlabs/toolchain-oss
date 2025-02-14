# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from dataclasses import dataclass
from functools import total_ordering


@total_ordering
@dataclass(frozen=True, order=False)
class ABI:
    """A specific ABI.

    `abi` may be `cp34m`, `abi3`, `none`, etc, but they all must have the same subject as they compete with one another.
    """

    abi: str

    @property
    def subject(self) -> str:
        return self.__class__.__name__

    def __eq__(self, other):
        if isinstance(other, ABI):
            return self.abi == other.abi
        return False

    def __lt__(self, other):
        if isinstance(other, ABI):
            return self.abi < other.abi
        try:
            return self.subject < other.subject
        except AttributeError:
            return NotImplemented
