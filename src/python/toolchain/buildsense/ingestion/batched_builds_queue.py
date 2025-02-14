# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import logging
import zlib
from collections.abc import Iterator
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePath
from typing import IO

from dateutil.parser import parse
from django.conf import settings

from toolchain.aws.s3 import S3
from toolchain.base.node_id import get_node_id
from toolchain.base.toolchain_error import ToolchainAssertion

_logger = logging.getLogger(__name__)


JsonBuildStats = dict[str, dict]


@dataclass
class QueuedBuilds:
    customer_id: str
    repo_id: str
    user_api_id: str
    request_id: str
    accepted_time: datetime.datetime

    builds: JsonBuildStats

    def get_build_stats(self) -> Iterator[dict]:
        yield from self.builds.values()

    @classmethod
    def from_json_data(cls, builds: dict, metadata: dict[str, str]) -> QueuedBuilds:
        accepted_time = parse(metadata["accepted_time"])
        return cls(
            customer_id=metadata["customer_id"],
            repo_id=metadata["repo_id"],
            user_api_id=metadata["user_api_id"],
            request_id=metadata["request_id"],
            accepted_time=accepted_time,
            builds=builds,
        )


class BatchedBuildsQueue:
    _TIMESTAMP_FMT = "%Y_%m_%d_%H_%M_%S"

    @classmethod
    def for_repo(cls, repo) -> BatchedBuildsQueue:
        return cls(customer_id=repo.customer_id, repo_id=repo.pk)

    def __init__(self, *, customer_id: str, repo_id: str) -> None:
        self._bucket = settings.BUILDSENSE_BUCKET
        self._base_path = PurePath(settings.BUILDSENSE_QUEUE_BASE_S3_PATH)
        self._node_id = get_node_id()
        self._customer_id = customer_id
        self._repo_id = repo_id
        self._s3 = S3()

    def __str__(self) -> str:
        return f"BatchedBuildsQueue(bucket={self._bucket} path={self._base_path} customer_id={self._customer_id} repo_id={self._repo_id})"

    def queue_builds(
        self,
        batched_builds: dict[str, dict] | IO[bytes],
        user_api_id: str,
        accepted_time: datetime.datetime,
        request_id: str,
    ) -> tuple[str, str]:
        time_str = accepted_time.strftime(self._TIMESTAMP_FMT)
        # TODO: There is still a collision potential here.
        key_path = self._base_path / "builds" / self._customer_id / self._repo_id / f"{time_str}_{self._node_id}.json"
        key = key_path.as_posix()
        metadata = {
            "customer_id": self._customer_id,
            "repo_id": self._repo_id,
            "user_api_id": user_api_id,
            "accepted_time": accepted_time.isoformat(),
            "node_id": self._node_id,
            "request_id": request_id,
            "compression": "zlib",
        }
        if isinstance(batched_builds, dict):
            # This is a temporary workaround, until I update the code to pass us a file pointer
            # (requires buildsense client changes)
            data = zlib.compress(json.dumps(batched_builds).encode())
            size = len(data)
            fp = BytesIO(data)
            mode = "dict"
        else:
            fp = batched_builds  # type: ignore[assignment]
            size = batched_builds.size  # type: ignore[attr-defined]
            mode = "fp"
        self._s3.upload_fileobj(bucket=self._bucket, key=key, fp=fp, content_type="application/json", metadata=metadata)
        _logger.info(f"queue_builds {size=} {mode=} {key=} {metadata=}")
        return self._bucket, key

    def get_builds(self, s3_key: str) -> QueuedBuilds:
        base_path = self._base_path.as_posix()
        if not s3_key.startswith(base_path):
            raise ToolchainAssertion(f"Unexpected {s3_key=} {base_path=}")
        data, s3_key_info = self._s3.get_content_with_object(self._bucket, s3_key)
        if s3_key_info.metadata:
            # New format
            metadata = s3_key_info.metadata
            builds = json.loads(zlib.decompress(data))
        else:
            # Old format
            json_data = json.loads(data)
            builds = json_data.pop("builds")
            metadata = json_data
        return QueuedBuilds.from_json_data(builds=builds, metadata=metadata)
