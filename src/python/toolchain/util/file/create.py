# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import os
from pathlib import Path

from toolchain.aws.s3 import S3
from toolchain.util.file.base import Directory, File, FileOrDirectory
from toolchain.util.file.errors import InvalidUrlError
from toolchain.util.file.local import LocalDirectory, LocalFile
from toolchain.util.file.s3 import S3Directory, S3File

_file_url_scheme = "file://"
_s3_url_scheme = "s3://"


def create(url: str) -> FileOrDirectory:
    return create_directory(url) if url.endswith("/") else create_file(url)


def create_file(url: str) -> File:
    """Create a File instance for the specified URL."""
    if url.endswith("/"):
        raise InvalidUrlError(f"URL representing a file must not end with a /: {url}")
    return _create_file_or_directory(url, LocalFile, S3File)


def create_directory(url: str) -> Directory:
    """Create a Directory instance for the specified URL."""
    if not url.endswith("/"):
        raise InvalidUrlError(f"URL representing a directory must end with a /: {url}")
    return _create_file_or_directory(url, LocalDirectory, S3Directory)


# Functions to create a local File or Directory instance from a pathlib Path.
# Note that since pathlib strips the trailing slash from directories, we require
# the caller to be explicit about whether they are referencing a file or a directory.


def create_file_from_path(path: Path) -> File:
    return create_file(path.as_uri())


def create_directory_from_path(path: Path) -> Directory:
    # Path strips off the trailing slash, so add it back.
    return create_directory(f"{path.as_uri()}/")


def _create_file_or_directory(url: str, local_cls, s3_cls):
    # Note that we don't use urllib.parse because that doesn't handle s3 URLs well, and it also
    # behaves inconveniently if a file:/// url omits the third slash (it correctly interprets that
    # as a host specification, but we don't support remote files).
    if url.startswith(_file_url_scheme):
        url_path = url[len(_file_url_scheme) :]
        if not url_path.startswith("/"):
            raise InvalidUrlError(f"Relative paths not supported for file:// URLs: {url}")
        filesystem_path = url_path.replace("/", os.path.sep) if os.path.sep != "/" else url_path
        return local_cls(filesystem_path)
    if url.startswith(_s3_url_scheme):
        return s3_cls(*S3.parse_s3_url(url))
    raise InvalidUrlError(f"URL scheme not supported for {url}")
