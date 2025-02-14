# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import re
from collections.abc import Iterator

import boto3

from toolchain.aws.s3 import S3
from toolchain.base.memo import memoized
from toolchain.util.file.base import Directory, File
from toolchain.util.file.errors import InvalidUrlError
from toolchain.util.file.local import LocalFile


@memoized
def _get_all_s3_regions():
    """Returns all regions that can contain S3 buckets.

    Uses boto3's client-side hard-coded data, so does not make a network call.
    """
    s = boto3.session.Session()
    return set(s.get_available_regions("s3"))


_bucket_re = re.compile(r"^(?:[^.]+\.)*(?P<region>[^.]+).toolchain.com$")


def get_region_from_bucket(bucket: str) -> str:
    mo = _bucket_re.match(bucket)
    if not mo:
        raise InvalidUrlError(f"Expected bucket name to end with <region_name>.toolchain.com but got: {bucket}")
    region = mo.group("region")
    if region not in _get_all_s3_regions():
        raise InvalidUrlError(f"Not a known region name: {bucket}")
    return region


class S3Mixin:
    """A mixin containing common implementation details for S3 files and directories."""

    def __init__(self, bucket: str, key: str):
        if key.startswith("/"):
            raise InvalidUrlError(f"S3 key must not start with /: {key}")
        self._bucket = bucket
        self._key = key
        self._s3 = S3(get_region_from_bucket(bucket))

    def url(self) -> str:
        return S3.get_s3_url(self._bucket, self._key)

    def path(self) -> str:
        return f"/{self._key}"

    def __eq__(self, other):
        return isinstance(other, type(self)) and self._bucket == other._bucket and self._key == other._key

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self._bucket, self._key))

    def __repr__(self):
        return f"{self.__class__.__name__}({self._bucket}, {self._key})"


class S3File(S3Mixin, File):
    def exists(self) -> bool:
        return self._s3.exists(self._bucket, self._key)

    def get_content(self) -> bytes:
        return self._s3.get_content(self._bucket, self._key)

    def set_content(self, buf: bytes):
        self._s3.upload_content(self._bucket, self._key, buf)

    def delete(self):
        self._s3.delete_object(self._bucket, self._key)

    # Note that S3File knows about LocalFile, so we can copy efficiently.

    def copy_to(self, dst: File):
        if isinstance(dst, S3File):
            self._s3.copy_object(self._bucket, self._key, dst._bucket, dst._key)
        elif isinstance(dst, LocalFile):
            self._s3.download_file(self._bucket, self._key, dst._os_path)
        else:
            raise InvalidUrlError(f"Cannot copy {self.__class__.__name__} to {type(dst).__name__}")

    def copy_from(self, src: File):
        if isinstance(src, S3File):
            self._s3.copy_object(src._bucket, src._key, self._bucket, self._key)
        elif isinstance(src, LocalFile):
            self._s3.upload_file(self._bucket, self._key, src._os_path)
        else:
            raise InvalidUrlError(f"Cannot copy {self.__class__.__name__} from {type(src).__name__}")


class S3Directory(S3Mixin, Directory):
    def get_file(self, suffix: str) -> File:
        return S3File(self._bucket, f"{self._key}{suffix}")

    def traverse(self) -> Iterator[File]:
        for key in self._s3.keys_with_prefix(self._bucket, self._key):
            yield S3File(self._bucket, key)

    def delete(self):
        self._s3.delete_objects_with_key_prefix(self._bucket, self._key)
