# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.util.file.create import InvalidUrlError, create_directory, create_file
from toolchain.util.file.local import LocalDirectory, LocalFile
from toolchain.util.file.s3 import S3Directory, S3File


def test_create_file():
    assert LocalFile("/foo/bar/baz") == create_file("file:///foo/bar/baz")
    assert S3File("ap-east-1.toolchain.com", "foo/bar/baz") == create_file("s3://ap-east-1.toolchain.com/foo/bar/baz")

    with pytest.raises(InvalidUrlError, match="URL scheme not supported for"):
        create_file("http://foobar.com/path/to/something")
    with pytest.raises(InvalidUrlError, match="Relative paths not supported for file:// URLs"):
        create_file("file://relative/path/to/something")  # Missing third slash after file://.
    with pytest.raises(InvalidUrlError, match="Not a known region name"):
        create_file("s3://bad-region-1.toolchain.com/path/to/something")
    with pytest.raises(InvalidUrlError, match="Expected bucket name"):
        create_file("s3://ap-east-1.notourdomain.com/path/to/something")


def test_create_directory():
    assert LocalDirectory("/foo/bar/baz/") == create_directory("file:///foo/bar/baz/")
    assert S3Directory("ap-east-1.toolchain.com", "foo/bar/baz/") == create_directory(
        "s3://ap-east-1.toolchain.com/foo/bar/baz/"
    )

    with pytest.raises(InvalidUrlError, match="URL representing a directory must end with a "):
        create_directory("file:///foo/bar/baz")
    with pytest.raises(InvalidUrlError, match="URL representing a directory must end with a "):
        create_directory("s3://ap-east-1.toolchain.com/foo/bar/baz")
