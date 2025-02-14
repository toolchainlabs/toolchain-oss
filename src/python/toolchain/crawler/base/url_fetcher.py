# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import hashlib
import logging
from contextlib import closing
from urllib.parse import urlparse

import requests
from django.conf import settings

from toolchain.aws.s3 import S3
from toolchain.base.contexttimer import Timer
from toolchain.base.datetime_tools import utcnow
from toolchain.base.hashutil import HashingReader, compute_sha256_hexdigest
from toolchain.crawler.base.chunk_adapter import ChunkAdapter
from toolchain.crawler.base.crawler_worker_base import CrawlerWorkerBase
from toolchain.crawler.base.models import FetchURL
from toolchain.django.webresource.models import WebResource
from toolchain.workflow.error import PermanentWorkException, TransientWorkException, WorkException

_logger = logging.getLogger(__name__)


class HashVerificationError(WorkException):
    def __init__(self, msg: str) -> None:
        super().__init__(self.Category.PERMANENT, msg)


class URLFetcher(CrawlerWorkerBase):
    """Base for worker that fetches a URL and schedules work to process it.

    Subclasses implement schedule_processing_work() to decide how to handle the content.
    """

    SHA1 = "SHA1"
    SHA256 = "SHA256"

    hash_algorithms = (SHA1, SHA256)
    DEFAULT_DOWNLOAD_CHUNK_SIZE = 64 * 1024

    work_unit_payload_cls = FetchURL

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._web_resource: WebResource | None = None
        self._status_code: int | None = None
        self._content_changed = True  # We make the conservative assumption.

    def transient_error_retry_delay(
        self, work_unit_payload: FetchURL, exception: Exception
    ) -> datetime.timedelta | None:
        delay = getattr(exception, "retry_delay", None) or datetime.timedelta(minutes=1)
        return delay

    @property
    def download_chunk_size(self) -> int:
        return self.DEFAULT_DOWNLOAD_CHUNK_SIZE

    def get_expected_hash(self, web_resource):
        """Return a pair (hash_algorithm, expected_hash_hexdigest) that the web resource is expected to match.

        hash_algorithm must be one of the hash_algorithms listed above. expected_hash_hexdigest must be a string of hex
        digits.

        Note that this is unrelated to the sha256_hexdigest we store on the WebResource.

        Subclasses may override if they support hash verification.
        """
        return None, None

    def schedule_processing_work(self, web_resource, changed):
        """Schedule any work required to process the content.

        Any work units and requirements created in this method will be committed in the same
        transaction as the work state and the WebResource creation/update.

        Implementations will typically schedule only if changed is True, but they may sometimes
        wish to schedule even nothing has changed (e.g., if new processes have been introduced
        and we want to run them on existing WebResources).

        :param WebResource web_resource: The WebResource for the fetched content.
        :param bool changed: Whether the content changed since the previous time we fetched it.
        """
        raise NotImplementedError()

    def lease_secs(self, work_unit_payload: FetchURL) -> float:
        # there are some large files (can be up to 1gb and more) so let the download take up to 20min
        return datetime.timedelta(minutes=20).total_seconds()

    def do_work(self, work_unit_payload: FetchURL) -> bool:
        freshness = utcnow()
        self._status_code = work_unit_payload.last_http_status
        url = work_unit_payload.url
        web_resource = WebResource.latest_by_url(url)
        old_etag = web_resource.etag if web_resource else WebResource.DEFAULT_ETAG
        try:
            with closing(requests.get(url, stream=True, headers={"If-None-Match": old_etag})) as response:
                # Status code of 304 means we have previously fetched this resource and the content has not changed.
                if response.status_code == 304 and web_resource:
                    web_resource.freshness = freshness
                    self._web_resource = web_resource
                    self._content_changed = False
                    self._status_code = response.status_code
                    return True

                content, content_url, sha256_hexdigest = self._process_response(url, response)
        except requests.RequestException as error:
            raise TransientWorkException(f"connection issue: {error!r}")
        # It is possible for badly behaved services to update etags when the content is not changed, so we always check
        # content and update the etags of previously fetched web resources if necessary. This also supports
        # refetching resources that do not support etags.
        self._status_code = response.status_code
        etag = response.headers.get("etag", WebResource.DEFAULT_ETAG)
        if web_resource and web_resource.sha256_hexdigest == sha256_hexdigest:
            web_resource.freshness = freshness
            web_resource.etag = etag
            # The encoding detection algorithm may have changed even if the content hasn't.
            web_resource.encoding = response.encoding or ""
            self._web_resource = web_resource
            self._content_changed = False
        else:
            self._web_resource = WebResource(
                url=work_unit_payload.url,
                sha256_hexdigest=sha256_hexdigest,
                freshness=freshness,
                encoding=response.encoding or "",
                compression=WebResource.IDENTITY,  # TODO: Support compression.
                content_url=content_url,
                content=content,
                etag=etag,
            )
        return True

    def _process_response(self, url, response) -> tuple[bytes | None, str, str]:
        if not response.ok:
            if response.status_code == 404 and self._status_code != 404:
                _logger.warning(f"got 404 for {url=} previous_status={self._status_code}")
                self._status_code = response.status_code
                raise TransientWorkException(
                    f"Got HTTP status {response.status_code} fetching {url}", retry_delay=datetime.timedelta(minutes=10)
                )
            exc_type = PermanentWorkException if 400 <= response.status_code < 500 else TransientWorkException
            self._status_code = response.status_code
            raise exc_type(f"Got HTTP status {response.status_code} fetching {url}")
        content_type = response.headers["content-type"]
        content_length = int(response.headers.get("content-length", -1))
        should_inline = (
            settings.INLINE_SMALL_WEBRESOURCE_TEXT_CONTENT
            and content_type.startswith("text/")
            and 0 <= content_length <= settings.MAX_INLINE_TEXT_SIZE
        )

        if should_inline:
            content = response.content
            sha256_hexdigest = compute_sha256_hexdigest(content)
            return content, "", sha256_hexdigest

        with Timer() as timer:
            fp = ChunkAdapter(response.iter_content(chunk_size=self.download_chunk_size))
            content_url, sha256_hexdigest = self._upload_content(url, content_type, fp)
        _logger.info(f"fetch_url_download {url=} {content_type=} {content_length=} latency={timer.elapsed:.3f}s")
        return None, content_url, sha256_hexdigest

    def _upload_content(self, url: str, content_type: str, fp) -> tuple[str, str]:
        path = urlparse(url).path
        if path.startswith("/"):
            path = path[1:]
        bucket = settings.WEBRESOURCE_BUCKET
        key = f"{settings.WEBRESOURCE_KEY_PREFIX}/webresource/{path}"
        hashing_reader = HashingReader(fp)
        s3 = S3()
        s3.upload_fileobj(bucket, key, hashing_reader, content_type=content_type)  # type: ignore[arg-type]
        content_url = s3.get_s3_url(bucket, key)
        sha256_hexdigest = hashing_reader.hexdigest()
        return content_url, sha256_hexdigest

    def rerun_requirers(self) -> bool:
        return self._content_changed

    def on_success(self, work_unit_payload):
        self._web_resource.save()
        work_unit_payload.web_resource = self._web_resource
        work_unit_payload.last_http_status = self._status_code
        self.schedule_processing_work(self._web_resource, self._content_changed)

    def on_failure(self, work_unit_payload):
        work_unit_payload.last_http_status = self._status_code

    # We don't currently reschedule this work type, but it can't hurt to be robust.
    def on_reschedule(self, work_unit_payload):
        work_unit_payload.last_http_status = self._status_code

    def verify_hash(self):
        hash_algorithm, expected_hash_hexdigest = self.get_expected_hash(self._web_resource)
        if hash_algorithm is None:
            return

        if hash_algorithm == self.SHA1:
            hasher = hashlib.sha1()
        else:
            raise HashVerificationError(f"Unsupported hash algorithm: {hash_algorithm} for {self._web_resource.url}")

        chunk_size = 64 * 1024
        with self._web_resource.content_reader() as fp:
            buf = fp.read(chunk_size)
            while len(buf) > 0:
                hasher.update(buf)
                buf = fp.read(chunk_size)
        actual_hash_hexdigest = hasher.hexdigest()
        if expected_hash_hexdigest != actual_hash_hexdigest:
            raise HashVerificationError(
                f"Expected {hash_algorithm} hash {expected_hash_hexdigest} but got {actual_hash_hexdigest} for {self._web_resource.content_reader}"
            )
