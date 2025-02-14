# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import os
import re
from collections.abc import Iterable, Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Callable

from toolchain.aws.aws_api import AWSService
from toolchain.base.fileutil import safe_mkdir, walk_local_directory
from toolchain.base.toolchain_error import ToolchainAssertion


@dataclass(frozen=True)
class S3KeyInfo:
    bucket: str
    key: str
    metadata: dict
    length: int
    content_type: str | None
    last_modified: datetime.datetime
    version_id: str | None

    @classmethod
    def from_s3_obj(cls, bucket: str, key: str, s3_obj: dict) -> S3KeyInfo:
        version_id = s3_obj.get("VersionId", "null")
        if version_id == "null":
            version_id = None
        return cls(
            bucket=bucket,
            key=key,
            metadata=s3_obj["Metadata"],
            content_type=s3_obj.get("ContentType"),
            length=s3_obj["ContentLength"],
            last_modified=s3_obj["LastModified"],
            version_id=version_id,
        )


class S3(AWSService):
    service = "s3"

    _s3_re = re.compile(r"^s3://(?P<bucket>[^/]+)/(?P<key>.+)$")

    @property
    def NoSuchKeyError(self):
        return self.client.exceptions.NoSuchKey

    @classmethod
    def get_s3_url(cls, bucket: str, key: str) -> str:
        return f"s3://{bucket}/{key}"

    @classmethod
    def parse_s3_url(cls, s3_url: str) -> tuple[str, str]:
        mo = cls._s3_re.match(s3_url)
        if mo is None:
            raise ToolchainAssertion(f"Not an S3 URL: {s3_url}")
        return mo.group("bucket"), mo.group("key")

    @classmethod
    def s3_url_to_http_url(cls, s3_url: str) -> str:
        bucket, key = cls.parse_s3_url(s3_url)
        return f"http://{bucket}.s3.amazonaws.com/{key}"

    def exists(self, bucket: str, key: str) -> bool:
        response = self.client.list_objects_v2(Bucket=bucket, Prefix=key)
        contents = response.get("Contents", [])
        return any(obj["Key"] == key for obj in contents)

    def url_exists(self, s3_url: str) -> bool:
        bucket, key = self.parse_s3_url(s3_url)
        return self.exists(bucket, key)

    def key_metadata_with_prefix(self, bucket: str, key_prefix: str, page_size: int | None = None) -> Iterable[dict]:
        """A generator for all the keys in a given bucket with a given prefix."""
        config = {"PageSize": page_size} if page_size else {}
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=key_prefix, PaginationConfig=config):
            # Note that empty pages can occur, in which case they may not have a `Contents` key.
            yield from page.get("Contents", [])

    def keys_with_prefix(self, bucket: str, key_prefix: str, page_size: int | None = None) -> Iterable[str]:
        for s3_key in self.key_metadata_with_prefix(bucket, key_prefix, page_size=page_size):
            yield s3_key["Key"]

    @contextmanager
    def body_reader(self, bucket: str, key: str) -> Iterator[IO[bytes]]:
        with closing(self.client.get_object(Bucket=bucket, Key=key)["Body"]) as streaming_body:
            yield streaming_body

    def get_content(self, bucket: str, key: str) -> bytes:
        with self.body_reader(bucket, key) as fp:
            return fp.read()

    def get_content_with_type(self, bucket: str, key: str) -> tuple[bytes, str]:
        content, info = self.get_content_with_object(bucket, key)
        content_type = info.content_type
        if not content_type:
            raise ToolchainAssertion(f"No content type for s3://{bucket}/{key}")
        return content, content_type

    def get_info(self, bucket: str, key: str) -> S3KeyInfo:
        s3_obj = self.client.get_object(Bucket=bucket, Key=key)
        return S3KeyInfo.from_s3_obj(bucket=bucket, key=key, s3_obj=s3_obj)

    def get_info_or_none(self, bucket: str, key: str) -> S3KeyInfo | None:
        try:
            return self.get_info(bucket, key)
        except self.NoSuchKeyError:
            return None

    def get_content_with_object(self, bucket: str, key: str) -> tuple[bytes, S3KeyInfo]:
        s3_obj = self.client.get_object(Bucket=bucket, Key=key)
        with closing(s3_obj["Body"]) as streaming_body:
            return streaming_body.read(), S3KeyInfo.from_s3_obj(bucket=bucket, key=key, s3_obj=s3_obj)

    def get_content_or_none(self, bucket: str, key: str) -> bytes | None:
        try:
            with self.body_reader(bucket, key) as fp:
                return fp.read()
        except self.NoSuchKeyError:
            return None

    def upload_file(
        self,
        bucket: str,
        key: str,
        path: str | Path,
        content_type: str | None = None,
        is_public: bool = False,
        cache_max_age: datetime.timedelta | None = None,
    ) -> None:
        # Note: this will overwrite any existing object at key.
        extra_args = {"ACL": "public-read"} if is_public else {}
        if content_type:
            extra_args["ContentType"] = content_type
        extra_kwargs = dict(ExtraArgs=extra_args) if extra_args else {}
        if cache_max_age:
            extra_args["CacheControl"] = f"max-age={int(cache_max_age.total_seconds())}"
        filename = path if isinstance(path, str) else path.as_posix()
        self.client.upload_file(Bucket=bucket, Key=key, Filename=filename, **extra_kwargs)

    def upload_fileobj(
        self,
        bucket: str,
        key: str,
        fp: IO[bytes],
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        # Note: this will overwrite any existing object at key.
        extra_kwargs = dict(ContentType=content_type) if content_type else {}
        if metadata:
            extra_kwargs["Metadata"] = metadata  # type: ignore[assignment]
        self.client.upload_fileobj(Bucket=bucket, Key=key, Fileobj=fp, ExtraArgs=extra_kwargs)

    def download_file(self, bucket: str, key: str, path: str) -> None:
        safe_mkdir(os.path.dirname(path))
        self.client.download_file(Bucket=bucket, Key=key, Filename=path)

    def download_fileobj(self, bucket: str, key: str, fp: IO[bytes]) -> None:
        self.client.download_fileobj(Bucket=bucket, Key=key, Fileobj=fp)

    def upload_json_str(self, bucket: str, key: str, json_str: str) -> None:
        # Note: this will overwrite any existing file at key.
        self.upload_content(bucket=bucket, key=key, content_bytes=json_str.encode(), content_type="application/json")

    def upload_content(
        self,
        bucket: str,
        key: str,
        content_bytes: bytes,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        # Note: this will overwrite any existing file at key.
        extra_kwargs = dict(ContentType=content_type) if content_type else {}
        if metadata:
            extra_kwargs["Metadata"] = metadata  # type: ignore[assignment]
        self.client.put_object(Body=content_bytes, Bucket=bucket, Key=key, **extra_kwargs)

    def copy_object(self, old_bucket: str, old_key: str, new_bucket: str, new_key: str) -> None:
        self.client.copy_object(CopySource={"Bucket": old_bucket, "Key": old_key}, Bucket=new_bucket, Key=new_key)

    def delete_object(self, bucket: str, key: str) -> None:
        self.client.delete_object(Bucket=bucket, Key=key)

    def delete_objects_with_key_prefix(self, bucket: str, key_prefix: str) -> None:
        self.resource.Bucket(bucket).objects.filter(Prefix=key_prefix).delete()

    def upload_directory(
        self, local_dir: str, bucket: str, key_prefix: str, callback: Callable[[Path, str], None] | None = None
    ):
        """Upload files under local_dir to objects with the corresponding key paths under key_prefix in bucket.

        If callback is provided it must be a two-arg callable, and is called with the local source path and target s3
        key of each file being uploaded.  This is useful e.g., for logging.
        """
        if not key_prefix.endswith("/"):
            raise ToolchainAssertion(f"key_prefix must end with /, but was {key_prefix}")

        for relpath, path in walk_local_directory(local_dir):
            key = (key_prefix / relpath).as_posix()
            if callback:
                callback(path, key)
            self.upload_file(bucket, key, path.as_posix())

    def download_directory(
        self, bucket: str, key_prefix: str, local_dir: str, callback: Callable[[str, str], None] | None = None
    ) -> None:
        """Download objects with the given key_prefix in bucket to the corresponding relative paths under local_dir.

        If callback is provided it must be a two-arg callable, and is called with the source s3 key and local target
        path of each file being downloaded.  This is useful e.g., for logging.
        """
        if not key_prefix.endswith("/"):
            raise ToolchainAssertion(f"key_prefix must end with /, but was {key_prefix}")

        for key in self.keys_with_prefix(bucket, key_prefix):
            relpath = key[len(key_prefix) :]
            if os.path.sep != "/":
                relpath = relpath.replace("/", os.path.sep)
            path = os.path.join(local_dir, relpath)
            if callback:
                callback(key, path)
            safe_mkdir(os.path.dirname(path))
            self.download_file(bucket, key, path)
