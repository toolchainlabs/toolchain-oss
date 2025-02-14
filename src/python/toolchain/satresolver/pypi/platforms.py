# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from dataclasses import dataclass
from functools import total_ordering

# NOTE: Do not rename this file `platform.py` It clobbers a module needed by pkg_resources and results in:
# `AttributeError: module 'platform' has no attribute 'mac_ver'`


@total_ordering
@dataclass(frozen=True, order=False)
class Platform:
    """A specific platform.

    `platform` may be `linux_x86_64`, `macosx_10_10_intel`, `manylinux1_x86_64`, etc, but they all must have the same
    subject as they compete with one another.
    """

    platform: str

    @property
    def subject(self) -> str:
        return self.__class__.__name__

    def __lt__(self, other):
        if isinstance(other, Platform):
            return self.platform < other.platform
        try:
            return self.subject < other.subject
        except AttributeError:
            return NotImplemented
