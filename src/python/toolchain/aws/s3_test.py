# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

import boto3
import pytest
from moto import mock_s3
from moto.core import DEFAULT_ACCOUNT_ID
from moto.s3.models import s3_backends

from toolchain.aws.s3 import S3
from toolchain.aws.test_utils.s3_utils import TEST_REGION, create_s3_bucket
from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion

_test_bucket = "testbucket"
_test_region = TEST_REGION


@pytest.fixture(autouse=True)
def _start_moto():
    with mock_s3():
        create_s3_bucket(_test_bucket)
        yield


@pytest.mark.parametrize(
    ("key", "s3_url", "http_url"),
    [
        ("dummy/path", "s3://testbucket/dummy/path", "http://testbucket.s3.amazonaws.com/dummy/path"),
        ("dummy/path/", "s3://testbucket/dummy/path/", "http://testbucket.s3.amazonaws.com/dummy/path/"),
        ("/dummy/path", "s3://testbucket//dummy/path", "http://testbucket.s3.amazonaws.com//dummy/path"),
    ],
)
def test_s3_url_functionality(key: str, s3_url: str, http_url: str) -> None:
    assert s3_url == S3.get_s3_url(_test_bucket, key)
    assert (_test_bucket, key) == S3.parse_s3_url(s3_url)
    assert http_url == S3.s3_url_to_http_url(s3_url)


@pytest.mark.parametrize("url", ["http://foo.com/bar/baz", "s4://blah/blah/blah/"])
def test_parse_s3_url_failure(url: str) -> None:
    with pytest.raises(ToolchainAssertion, match=f"Not an S3 URL: {url}"):
        S3.parse_s3_url(url)


def test_exists_and_delete() -> None:
    s3 = S3(_test_region)
    test_key = "foo/bar.txt"
    test_url = "s3://testbucket/foo/bar.txt"

    assert not s3.exists(_test_bucket, test_key)
    assert not s3.url_exists(test_url)
    s3.upload_content(_test_bucket, test_key, b"")
    assert s3.exists(_test_bucket, test_key)
    assert s3.url_exists(test_url)
    s3.delete_object(_test_bucket, test_key)
    assert not s3.exists(_test_bucket, test_key)
    assert not s3.url_exists(test_url)


def test_keys_with_prefix() -> None:
    s3 = S3(_test_region)
    s3.upload_content(_test_bucket, "foo/bar.txt", b"")
    s3.upload_content(_test_bucket, "foo/baz/qux.txt", b"")
    s3.upload_content(_test_bucket, "not/under/foo/a.txt", b"")
    s3.upload_content(_test_bucket, "foowithoutaslash", b"")

    assert set(s3.keys_with_prefix(_test_bucket, "foo/")) == {"foo/bar.txt", "foo/baz/qux.txt"}
    assert set(s3.keys_with_prefix(_test_bucket, "foo")) == {"foo/bar.txt", "foo/baz/qux.txt", "foowithoutaslash"}


def test_upload_json_str() -> None:
    s3 = S3(_test_region)
    s3.upload_json_str(_test_bucket, "mail/cancel-mail.txt", '{"andrea-doria": ["marble-rye", "shrinkage"]}')
    assert s3.get_content(_test_bucket, "mail/cancel-mail.txt") == b'{"andrea-doria": ["marble-rye", "shrinkage"]}'
    s3_obj = s3.client.get_object(Bucket=_test_bucket, Key="mail/cancel-mail.txt")
    assert s3_obj["ContentType"] == "application/json"


def test_reading_and_writing_content() -> None:
    s3 = S3(_test_region)
    s3.upload_content(_test_bucket, "foo/bar.txt", b"Hello")
    assert s3.get_content(_test_bucket, "foo/bar.txt") == b"Hello"


def test_get_content_or_none() -> None:
    s3 = S3(_test_region)
    assert s3.get_content_or_none(_test_bucket, "foo/bosco.txt") is None
    s3.upload_content(_test_bucket, "foo/bosco.txt", b"no soup for you")
    assert s3.get_content_or_none(_test_bucket, "foo/bosco.txt") == b"no soup for you"
    assert s3.get_content_or_none(_test_bucket, "foo/jerry.txt") is None


def _assert_permissions(s3_rsc, expected_grants: int, *expected_permissions: str) -> None:
    grants = s3_rsc.Acl().grants
    assert len(grants) == expected_grants
    assert {grant["Permission"] for grant in grants} == set(expected_permissions)


def test_upload_file() -> None:
    s3 = S3(_test_region)
    with NamedTemporaryFile() as tmpfile:
        tmpfile.write(b"Hello")
        tmpfile.seek(0)
        s3.upload_file(_test_bucket, "from_file", tmpfile.name)
    s3_rsc = boto3.resource("s3").Object(_test_bucket, "from_file")
    _assert_permissions(s3_rsc, 1, "FULL_CONTROL")
    s3_obj = s3_rsc.get()
    assert s3_obj["ContentType"] == "binary/octet-stream"
    assert s3_obj["Body"].read() == b"Hello"


def test_upload_fileobj() -> None:
    s3 = S3(_test_region)
    with NamedTemporaryFile() as tmpfile:
        tmpfile.write(b"Hello")
        tmpfile.seek(0)
        s3.upload_fileobj(_test_bucket, "from_fileobj", tmpfile)
        assert s3.get_content(_test_bucket, "from_fileobj") == b"Hello"
    content, s3_obj_info = s3.get_content_with_object(_test_bucket, "from_fileobj")
    assert content == b"Hello"
    assert s3_obj_info.key == "from_fileobj"
    assert s3_obj_info.bucket == "testbucket"
    assert s3_obj_info.content_type == "binary/octet-stream"
    assert s3_obj_info.length == len(content) == 5
    assert not s3_obj_info.metadata


def test_upload_fileobj_with_metadata() -> None:
    s3 = S3(_test_region)
    with NamedTemporaryFile() as tmpfile:
        tmpfile.write(b"I can't spare a square")
        tmpfile.seek(0)
        s3.upload_fileobj(_test_bucket, "spare", tmpfile, metadata={"pez": "dispenser"})
    content, s3_obj_info = s3.get_content_with_object(_test_bucket, "spare")
    assert content == b"I can't spare a square"
    assert s3_obj_info.key == "spare"
    assert s3_obj_info.bucket == "testbucket"
    assert s3_obj_info.content_type == "binary/octet-stream"
    assert s3_obj_info.length == len(content) == 22
    assert s3_obj_info.metadata == {"pez": "dispenser"}


def test_upload_fileobj_with_metadata_and_content_type() -> None:
    s3 = S3(_test_region)
    with NamedTemporaryFile() as tmpfile:
        tmpfile.write(b"I can't spare a square")
        tmpfile.seek(0)
        s3.upload_fileobj(_test_bucket, "spare", tmpfile, content_type="text/plain", metadata={"pez": "dispenser"})
    content, s3_obj_info = s3.get_content_with_object(_test_bucket, "spare")
    assert content == b"I can't spare a square"
    assert s3_obj_info.key == "spare"
    assert s3_obj_info.bucket == "testbucket"
    assert s3_obj_info.content_type == "text/plain"
    assert s3_obj_info.length == len(content) == 22
    assert s3_obj_info.metadata == {"pez": "dispenser"}


def test_upload_file_public_with_content_type() -> None:
    s3 = S3(_test_region)
    with NamedTemporaryFile() as tmpfile:
        tmpfile.write(b"Hello")
        tmpfile.seek(0)
        s3.upload_file(_test_bucket, "hello-newman.txt", tmpfile.name, content_type="text/plain", is_public=True)
    s3_rsc = boto3.resource("s3").Object(_test_bucket, "hello-newman.txt")
    _assert_permissions(s3_rsc, 2, "FULL_CONTROL", "READ")
    s3_obj = s3_rsc.get()
    assert s3_obj["ContentType"] == "text/plain"
    assert s3_obj["Body"].read() == b"Hello"


def test_upload_content_with_metadata():
    s3 = S3(_test_region)
    s3.upload_content(
        _test_bucket, "glamor-magazine", b"My mother caught me", content_type="text/plain", metadata={"puffy": "shirt"}
    )
    content, s3_obj_info = s3.get_content_with_object(_test_bucket, "glamor-magazine")
    assert content == b"My mother caught me"
    assert s3_obj_info.key == "glamor-magazine"
    assert s3_obj_info.bucket == "testbucket"
    assert s3_obj_info.content_type == "text/plain"
    assert s3_obj_info.length == len(content) == 19
    assert s3_obj_info.metadata == {"puffy": "shirt"}


def test_download_file(tmp_path: Path) -> None:
    s3 = S3(_test_region)
    s3.upload_content(_test_bucket, "somefile", b"Hello")

    path = tmp_path / "foo" / "bar.txt"
    path.parent.mkdir()
    s3.download_file(_test_bucket, "somefile", path.as_posix())
    with open(path, "rb") as fp:
        assert fp.read() == b"Hello"

    with open(path, "wb") as fp:
        s3.download_fileobj(_test_bucket, "somefile", fp)
    with open(path, "rb") as fp:
        assert fp.read() == b"Hello"


def test_get_content_with_type():
    s3 = S3(_test_region)
    s3.upload_content(_test_bucket, "glamor-magazine", b"My mother caught me", content_type="text/seinfeld")
    content, content_type = s3.get_content_with_type(_test_bucket, "glamor-magazine")
    assert content == b"My mother caught me"
    assert content_type == "text/seinfeld"


def test_get_content_with_type_missing_type():
    s3 = S3(_test_region)
    s3.upload_content(_test_bucket, "pez", b"dispenser", content_type="")
    # AWS always sets Content-Type even if not provided via the api (it will be "binary/octet-stream")
    # Moto does the same, so in order to simulate this state we have to access the moto backend and mess with it.
    # See: https://github.com/spulec/moto/pull/4439
    del s3_backends[DEFAULT_ACCOUNT_ID]["global"].buckets[_test_bucket].keys["pez"]._metadata["Content-Type"]
    with pytest.raises(ToolchainAssertion, match="No content type for s3://testbucket/pez"):
        s3.get_content_with_type(_test_bucket, "pez")


def test_copy_object() -> None:
    s3 = S3(_test_region)
    src_key = "src/key"
    dst_key = "dst/key"

    s3.upload_content(_test_bucket, src_key, b"Hello")
    s3.copy_object(_test_bucket, src_key, _test_bucket, dst_key)
    assert s3.get_content(_test_bucket, dst_key) == b"Hello"

    # Now test across buckets.
    other_bucket = "otherbucket"
    create_s3_bucket(other_bucket)
    s3.copy_object(_test_bucket, src_key, other_bucket, dst_key)
    assert s3.get_content(other_bucket, dst_key) == b"Hello"


def test_upload_directory(tmp_path: Path) -> None:
    def write_file(rel_path, content):
        path = tmp_path / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as fp:
            fp.write(content)

        write_file("foo.txt", b"Foo")
        write_file(os.path.join("bar", "baz.txt"), b"")
        write_file(os.path.join("bar", "qux", "hello_world.txt"), b"Hello, World")

        s3 = S3(_test_region)
        key_prefix = "test/upload/directory/"
        s3.upload_directory(tmp_path.as_posix(), _test_bucket, key_prefix)

        def check_content(rel_key, expected_content):
            key = f"{key_prefix}{rel_key}"
            assert s3.exists(_test_bucket, key)
            assert expected_content == s3.get_content(_test_bucket, key)

        check_content("foo.txt", b"Foo")
        check_content("bar/baz.txt", b"")
        check_content("bar/qux/hello_world.txt", b"Hello, World")


def test_download_directory(tmp_path: Path) -> None:
    s3 = S3(_test_region)
    key_prefix = "test/download/directory/"

    def write_object(rel_key, content):
        key = f"{key_prefix}{rel_key}"
        s3.upload_content(_test_bucket, key, content)

    write_object("foo.txt", b"Foo")
    write_object("bar/baz.txt", b"")
    write_object("bar/qux/hello_world.txt", b"Hello, World")

    s3.download_directory(_test_bucket, key_prefix, tmp_path.as_posix())

    def check_content(rel_path, expected_content):
        path = tmp_path / rel_path
        assert path.exists() is True
        with open(path, "rb") as fp:
            assert expected_content == fp.read()

    check_content("foo.txt", b"Foo")
    check_content(os.path.join("bar", "baz.txt"), b"")
    check_content(os.path.join("bar", "qux", "hello_world.txt"), b"Hello, World")


def test_get_info():
    s3 = S3(_test_region)
    content = b"My mother caught me"
    s3.upload_content(_test_bucket, "glamor-magazine", content, content_type="text/seinfeld")
    info = s3.get_info(_test_bucket, "glamor-magazine")
    assert info.bucket == _test_bucket
    assert info.key == "glamor-magazine"
    assert info.length == len(content) == 19
    assert not info.metadata
    assert info.last_modified.timestamp() == pytest.approx(utcnow().timestamp())
    assert info.version_id is None


def test_get_info_or_none():
    s3 = S3(_test_region)
    content = b"My mother caught me!!!"
    s3.upload_content(
        _test_bucket, "glamor-magazine", content, content_type="text/seinfeld", metadata={"pez": "dispenser"}
    )
    info = s3.get_info_or_none(_test_bucket, "glamor-magazine")
    assert info is not None
    assert info.bucket == _test_bucket
    assert info.key == "glamor-magazine"
    assert info.length == len(content) == 22
    assert info.metadata == {"pez": "dispenser"}
    assert info.last_modified.timestamp() == pytest.approx(utcnow().timestamp())
    assert info.version_id is None


def test_get_info_or_none_no_object():
    s3 = S3(_test_region)
    s3.upload_content(_test_bucket, "glamor-magazine", b"soup", content_type="text/seinfeld")
    info = s3.get_info_or_none(_test_bucket, "glamor-magazine-2")
    assert info is None
