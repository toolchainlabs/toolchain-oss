# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import hashlib


def compute_sha256_hexdigest(buf):
    """Compute the sha256 hexdigest for the given content."""
    hasher = hashlib.sha256()
    hasher.update(buf)
    return hasher.hexdigest()


class HashingReader:
    """A wrapper around a file-like object that computes a hash of read content on-the-fly.

    Allows us to compute a hash while streaming content from a request body to S3, without having to stream twice.
    """

    def __init__(self, underlying_fp, hasher_type=hashlib.sha256):
        """
        :param underlying_fp: The file-like object to wrap. Must support read(n).
        :param hasher_type: A no-arg callable for constructing a hasher.
        """
        self._underlying_fp = underlying_fp
        self._hasher = hasher_type()

    def read(self, n=-1):
        buf = self._underlying_fp.read(n)
        self._hasher.update(buf)
        return buf

    def hexdigest(self):
        return self._hasher.hexdigest()
