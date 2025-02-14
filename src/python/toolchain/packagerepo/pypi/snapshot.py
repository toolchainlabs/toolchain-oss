# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterable

from toolchain.util.leveldb.dataset import Dataset


class Snapshot(Dataset):
    """Code to query a PyPI snapshot leveldb."""

    def to_json(self):
        return json.dumps(self.to_dict())

    def to_dict(self):
        ret = {}
        for package_name, versions in self._db.iterator():
            ret[package_name.decode()] = _versions_list(versions)
        return ret

    def get_package_names(self) -> Iterable[str]:
        for package_name, _ in self._db.iterator():
            yield package_name

    def get_versions_for_package(self, package_name: str) -> Iterable[str]:
        versions: bytes = self._db.get(package_name.encode())
        if not versions:
            return []
        return _versions_list(versions)

    def diff(self, other: Snapshot):
        """Return a dict of package_name->versions for versions that exist in this snapshot but not in other."""
        ret = {}
        this_iter = self._db.iterator()
        other_iter = other._db.iterator()
        # Advance through both iterators together.
        other_package, other_versions = b"", b""
        with contextlib.suppress(StopIteration):
            while True:
                this_package, this_versions = next(this_iter)
                while other_package < this_package:
                    try:
                        other_package, other_versions = next(other_iter)
                    except StopIteration:
                        ret[this_package.decode()] = _versions_list(this_versions)
                        for this_package, this_versions in this_iter:
                            ret[this_package.decode()] = _versions_list(this_versions)
                        raise
                if other_package == this_package:
                    version_deltas = set(_versions_list(this_versions)).difference(_versions_list(other_versions))
                    if version_deltas:
                        ret[this_package.decode()] = sorted(version_deltas)
                else:
                    ret[this_package.decode()] = _versions_list(this_versions)
        return ret


def _versions_list(versions: bytes):
    return versions.decode().split("\t")
