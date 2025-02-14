# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from pathlib import Path

import pytest
from moto import mock_s3

from toolchain.aws.s3 import S3
from toolchain.aws.test_utils.s3_utils import TEST_REGION, create_s3_bucket
from toolchain.util.file.errors import InvalidUrlError
from toolchain.util.file.local import LocalDirectory, LocalFile
from toolchain.util.file.s3 import S3Directory, S3File, get_region_from_bucket

_test_bucket = f"testbucket.{TEST_REGION}.toolchain.com"


# Some of the tests don't actually need the s3 fixture, but they get it anyway because of autouse=True, which
# we use so we're sure that no tests in this file accidentally access real s3 resources. Better safe than sorry!
@pytest.fixture(autouse=True)
def s3():
    with mock_s3():
        create_s3_bucket(_test_bucket)
        yield S3(TEST_REGION)


@pytest.mark.parametrize(
    ("bucket", "region"),
    [
        ("foo.us-east-1.toolchain.com", "us-east-1"),
        ("us-east-1.toolchain.com", "us-east-1"),
        ("foo.bar.us-east-1.toolchain.com", "us-east-1"),
        ("eu-central-1.foo.us-east-1.toolchain.com", "us-east-1"),
        ("foo.eu-central-1.toolchain.com", "eu-central-1"),
    ],
)
def test_get_region_from_bucket_success(bucket, region):
    assert region == get_region_from_bucket(bucket)


@pytest.mark.parametrize(
    ("bucket", "error"),
    [
        ("foo.toolchain.com", "Not a known region name"),
        ("us-east-1.barbaz.com", "Expected bucket name to end with"),
        ("us.east.1.toolchain.com", "Not a known region name"),
    ],
)
def test_get_region_from_bucket_failure(bucket, error):
    with pytest.raises(InvalidUrlError, match=error):
        get_region_from_bucket(bucket)


def test_url_and_path():
    file = S3File(_test_bucket, "foo/bar/baz")
    assert file.url() == "s3://testbucket.ap-northeast-1.toolchain.com/foo/bar/baz"
    assert file.path() == "/foo/bar/baz"


def test_file_exists_and_delete(s3):
    key = "foo/bar.txt"
    file = S3File(_test_bucket, key)
    assert not file.exists()
    s3.upload_content(_test_bucket, key, b"")
    assert file.exists()
    file.delete()
    assert not file.exists()


def test_file_set_and_get_content():
    content = b"Hello, World!"
    file = S3File(_test_bucket, "foo/bar.txt")
    file.set_content(content)
    assert content == S3File(_test_bucket, "foo/bar.txt").get_content()


@pytest.mark.parametrize(
    "target_bucket",
    [_test_bucket, f"other.{_test_bucket}"],  # Test copying in the same bucket.  # Test copying across buckets.
)
def test_file_copy_s3_to_s3(s3, target_bucket):
    content = b"Hello, World!"
    if target_bucket != _test_bucket:
        create_s3_bucket(target_bucket)
    src_key = "foo/src.txt"
    dst_key = "bar/dst.txt"

    src = S3File(_test_bucket, src_key)
    dst = S3File(target_bucket, dst_key)

    assert not src.exists()
    assert not dst.exists()

    s3.upload_content(_test_bucket, src_key, content)
    assert src.exists()
    assert not dst.exists()

    src.copy_to(dst)
    assert src.exists()
    assert dst.exists()
    assert content == dst.get_content()

    dst.delete()
    assert src.exists()
    assert not dst.exists()

    dst.copy_from(src)
    assert src.exists()
    assert dst.exists()
    assert content == dst.get_content()


def test_file_copy_local_to_s3(tmp_path: Path) -> None:
    content = b"Hello, World!"

    src_path = tmp_path / "foo" / "src.txt"
    dst_key = "bar/dst.txt"

    src_path.parent.mkdir(parents=True)
    src = LocalFile(src_path.as_posix())
    dst = S3File(_test_bucket, dst_key)

    assert not src.exists()
    assert not dst.exists()

    with src_path.open(mode="wb") as fp:
        fp.write(content)
    assert src.exists()
    assert not dst.exists()

    src.copy_to(dst)
    assert src.exists()
    assert dst.exists()
    assert content == dst.get_content()

    dst.delete()
    assert src.exists()
    assert not dst.exists()

    dst.copy_from(src)
    assert src.exists()
    assert dst.exists()
    assert content == dst.get_content()


def test_file_copy_s3_to_local(s3, tmp_path: Path) -> None:
    content = b"Hello, World!"

    src_key = "foo/src.txt"
    dst_path = tmp_path / "bar" / "dst.txt"
    dst_path.parent.mkdir(parents=True)

    src = S3File(_test_bucket, src_key)
    dst = LocalFile(dst_path.as_posix())

    assert not src.exists()
    assert not dst.exists()

    s3.upload_content(_test_bucket, src_key, content)
    assert src.exists()
    assert not dst.exists()

    src.copy_to(dst)
    assert src.exists()
    assert dst.exists()
    assert content == dst.get_content()

    dst.delete()
    assert src.exists()
    assert not dst.exists()

    dst.copy_from(src)
    assert src.exists()
    assert dst.exists()
    assert content == dst.get_content()


def test_directory_get_file() -> None:
    assert S3File(_test_bucket, "foo/bar/baz/qux.txt") == S3Directory(_test_bucket, "foo/bar/").get_file("baz/qux.txt")


def test_directory_traverse(s3) -> None:
    dir_key_prefix = "dir/key/prefix/"
    relkeys = {"foo.txt", "bar/baz.txt", "bar/qux/quux.txt", "a/b/c/d"}
    keys = {f"{dir_key_prefix}{relkey}" for relkey in relkeys}
    for key in keys:
        s3.upload_content(_test_bucket, key, b"")

    expected_files = {S3File(_test_bucket, key) for key in keys}
    assert expected_files == set(S3Directory(_test_bucket, dir_key_prefix).traverse())


def test_directory_delete(s3) -> None:
    s3.upload_content(_test_bucket, "dir/foo", b"")
    s3.upload_content(_test_bucket, "dir/foo/bar/baz", b"")
    assert s3.exists(_test_bucket, "dir/foo")
    assert s3.exists(_test_bucket, "dir/foo/bar/baz")
    S3Directory(_test_bucket, "dir/").delete()
    assert not s3.exists(_test_bucket, "dir/foo")
    assert not s3.exists(_test_bucket, "dir/foo/bar/baz")


@pytest.mark.parametrize(
    "target_bucket",
    [_test_bucket, f"other.{_test_bucket}"],  # Test copying in the same bucket.  # Test copying across buckets.
)
def test_directory_copy_s3_to_s3(target_bucket: str, s3) -> None:
    if target_bucket != _test_bucket:
        create_s3_bucket(target_bucket)

    s3.upload_content(_test_bucket, "src/foo/bar.txt", b"bar")
    s3.upload_content(_test_bucket, "src/baz/qux.txt", b"qux")
    s3.upload_content(_test_bucket, "src/baz/quux.txt", b"quux")

    src = S3Directory(_test_bucket, "src/")
    dst = S3Directory(target_bucket, "dst/")

    src.copy_to(dst)

    assert S3File(target_bucket, "dst/foo/bar.txt").get_content() == b"bar"
    assert S3File(target_bucket, "dst/baz/qux.txt").get_content() == b"qux"
    assert S3File(target_bucket, "dst/baz/quux.txt").get_content() == b"quux"

    src.delete()
    src.copy_from(dst)
    assert S3File(_test_bucket, "src/foo/bar.txt").get_content() == b"bar"
    assert S3File(_test_bucket, "src/baz/qux.txt").get_content() == b"qux"
    assert S3File(_test_bucket, "src/baz/quux.txt").get_content() == b"quux"


def test_directory_copy_local_to_s3(s3, tmp_path: Path) -> None:
    src_path = tmp_path / "src"
    src_path.mkdir()
    (src_path / "foo").mkdir()
    with (src_path / "foo" / "bar.txt").open(mode="wb") as fp:
        fp.write(b"bar")
    (src_path / "baz").mkdir()
    with (src_path / "baz" / "qux.txt").open(mode="wb") as fp:
        fp.write(b"qux")
    with (src_path / "baz" / "quux.txt").open(mode="wb") as fp:
        fp.write(b"quux")

    src = LocalDirectory(src_path.as_posix())
    dst = S3Directory(_test_bucket, "dst/")
    src.copy_to(dst)

    assert S3File(_test_bucket, "dst/foo/bar.txt").get_content() == b"bar"
    assert S3File(_test_bucket, "dst/baz/qux.txt").get_content() == b"qux"
    assert S3File(_test_bucket, "dst/baz/quux.txt").get_content() == b"quux"


def test_directory_copy_s3_to_local(s3, tmp_path: Path) -> None:
    s3.upload_content(_test_bucket, "src/foo/bar.txt", b"bar")
    s3.upload_content(_test_bucket, "src/baz/qux.txt", b"qux")
    s3.upload_content(_test_bucket, "src/baz/quux.txt", b"quux")

    src = S3Directory(_test_bucket, "src/")

    dst_path = tmp_path / "dst"
    dst = LocalDirectory(dst_path.as_posix())

    src.copy_to(dst)

    assert LocalFile((dst_path / "foo" / "bar.txt").as_posix()).get_content() == b"bar"
    assert LocalFile((dst_path / "baz" / "qux.txt").as_posix()).get_content() == b"qux"
    assert LocalFile((dst_path / "baz" / "quux.txt").as_posix()).get_content() == b"quux"
