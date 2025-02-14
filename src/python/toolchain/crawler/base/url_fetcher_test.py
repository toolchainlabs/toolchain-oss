# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime
import gzip
import re

import pytest
from moto import mock_s3
from requests.exceptions import ConnectionError

from toolchain.aws.s3 import S3
from toolchain.aws.test_utils.s3_utils import assert_bucket_empty, create_s3_bucket
from toolchain.base.datetime_tools import utcnow
from toolchain.crawler.base.models import FetchURL
from toolchain.crawler.base.url_fetcher import URLFetcher
from toolchain.django.webresource.models import WebResource
from toolchain.workflow.error import PermanentWorkException, TransientWorkException


@pytest.mark.django_db()
class TestURLFetcher:
    _BUCKET = "fake-web-resource-bucket"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3():
            create_s3_bucket(self._BUCKET)
            yield

    def _add_response(self, responses, url: str, content: str, compress: bool = False) -> None:
        headers = {"ETag": "Kalahari"}
        body = content.encode()
        if compress:
            body = gzip.compress(body)
            headers["Content-Encoding"] = "gzip"
        headers["Content-Length"] = str(len(body))
        responses.add(responses.GET, url, stream=True, body=body, adding_headers=headers)

    def test_fetch_url_no_inline(self, responses) -> None:
        s3 = S3()
        self._add_response(responses, "https://jerry.com/festivus.txt", "The went like hotcakes")
        payload = FetchURL.get_or_create("https://jerry.com/festivus.txt")
        worker = URLFetcher()
        assert worker.do_work(payload) is True
        assert len(responses.calls) == 1
        request = responses.calls[0].request
        assert request.headers["If-None-Match"] == "Not Set"
        assert WebResource.objects.count() == 0
        assert s3.exists(self._BUCKET, key="del/boca/vista/webresource/festivus.txt") is True
        content = s3.get_content(self._BUCKET, key="del/boca/vista/webresource/festivus.txt")
        assert content == b"The went like hotcakes"
        assert worker._status_code == 200
        web_resource = worker._web_resource
        assert web_resource is not None
        assert web_resource.url == "https://jerry.com/festivus.txt"
        assert web_resource.sha256_hexdigest == "e113ffdce36886616d60d7762de35c0d10d96d80a6203a628a9a148d69d12e3a"
        assert web_resource.encoding == "ISO-8859-1"
        assert web_resource.etag == "Kalahari"
        assert web_resource.content_url == "s3://fake-web-resource-bucket/del/boca/vista/webresource/festivus.txt"
        assert web_resource.content is None
        assert web_resource.compression == WebResource.IDENTITY
        assert web_resource.freshness.timestamp() == pytest.approx(utcnow().timestamp())

    def test_fetch_url_inline(self, responses, settings) -> None:
        settings.MAX_INLINE_TEXT_SIZE = 300
        self._add_response(responses, "https://jerry.com/pole.txt", "Death Blow")
        payload = FetchURL.get_or_create("https://jerry.com/pole.txt")
        worker = URLFetcher()
        assert worker.do_work(payload) is True
        assert len(responses.calls) == 1
        request = responses.calls[0].request
        assert request.headers["If-None-Match"] == "Not Set"
        assert WebResource.objects.count() == 0
        assert worker._status_code == 200
        web_resource = worker._web_resource
        assert web_resource is not None
        assert web_resource.url == "https://jerry.com/pole.txt"
        assert web_resource.sha256_hexdigest == "e7e2335e9fc637c1dbae09b10f099748e5b3c840cfa196e4fcc2102367742e31"
        assert web_resource.encoding == "ISO-8859-1"
        assert web_resource.etag == "Kalahari"
        assert web_resource.content_url == ""
        assert web_resource.content == b"Death Blow"
        assert web_resource.compression == WebResource.IDENTITY
        assert web_resource.freshness.timestamp() == pytest.approx(utcnow().timestamp())
        assert_bucket_empty(S3(), self._BUCKET)

    def test_fetch_url_gzip_no_inline(self, responses) -> None:
        s3 = S3()
        self._add_response(responses, "https://jerry.com/tinsel.txt", "Del Boca Vista" * 100, compress=True)
        payload = FetchURL.get_or_create("https://jerry.com/tinsel.txt")
        worker = URLFetcher()
        assert worker.do_work(payload) is True
        assert WebResource.objects.count() == 0
        assert s3.exists(self._BUCKET, key="del/boca/vista/webresource/tinsel.txt") is True
        content = s3.get_content(self._BUCKET, key="del/boca/vista/webresource/tinsel.txt")
        assert content == b"Del Boca Vista" * 100
        assert worker._status_code == 200
        web_resource = worker._web_resource
        assert web_resource is not None
        assert web_resource.url == "https://jerry.com/tinsel.txt"
        assert web_resource.sha256_hexdigest == "601f181aef8af6d28ac620fb596f1dfd09a0beb508e5c936e310c45762eab0c4"
        assert web_resource.encoding == "ISO-8859-1"
        assert web_resource.etag == "Kalahari"
        assert web_resource.content_url == "s3://fake-web-resource-bucket/del/boca/vista/webresource/tinsel.txt"
        assert web_resource.content is None
        # The downloaded content was gzipped, but we store it uncompressed.
        assert web_resource.compression == WebResource.IDENTITY
        assert web_resource.freshness.timestamp() == pytest.approx(utcnow().timestamp())

    def test_fetch_url_gzip_inline(self, responses, settings) -> None:
        settings.MAX_INLINE_TEXT_SIZE = 3000
        self._add_response(responses, "https://jerry.com/feats-of-strength.txt", "Mandelbaum" * 10, compress=True)
        payload = FetchURL.get_or_create("https://jerry.com/feats-of-strength.txt")
        worker = URLFetcher()
        assert worker.do_work(payload) is True
        assert WebResource.objects.count() == 0
        assert worker._status_code == 200
        web_resource = worker._web_resource
        assert web_resource is not None
        assert web_resource.url == "https://jerry.com/feats-of-strength.txt"
        assert web_resource.sha256_hexdigest == "d8c239f122f51ede220c52fc5fc12f6f156552314459d38e490b3a1f7ec293c6"
        assert web_resource.encoding == "ISO-8859-1"
        assert web_resource.etag == "Kalahari"
        assert web_resource.content_url == ""
        assert web_resource.content == b"Mandelbaum" * 10
        # The downloaded content was gzipped, but we store it uncompressed.
        assert web_resource.compression == WebResource.IDENTITY
        assert web_resource.freshness.timestamp() == pytest.approx(utcnow().timestamp())
        assert_bucket_empty(S3(), self._BUCKET)

    def test_fetch_existing_url_content_changed(self, responses) -> None:
        WebResource.objects.create(
            url="https://kramer.com/cigars.data",
            sha256_hexdigest="Nexus of the universe",
            freshness=datetime.datetime(2020, 8, 22, 10, 22, 50, tzinfo=datetime.timezone.utc),
            encoding="",
            compression=WebResource.IDENTITY,
            content_url="3://fake-web-resource-bucket/del/boca/vista/webresource/cigars.data",
            content=None,
            etag="Pony",
        )
        s3 = S3()
        self._add_response(responses, "https://kramer.com/cigars.data", "Look to the cookie")
        payload = FetchURL.get_or_create("https://kramer.com/cigars.data")
        worker = URLFetcher()
        assert worker.do_work(payload) is True
        assert len(responses.calls) == 1
        request = responses.calls[0].request
        assert request.headers["If-None-Match"] == "Pony"
        assert WebResource.objects.count() == 1
        assert s3.exists(self._BUCKET, key="del/boca/vista/webresource/cigars.data") is True
        content = s3.get_content(self._BUCKET, key="del/boca/vista/webresource/cigars.data")
        assert content == b"Look to the cookie"
        assert worker._content_changed is True
        assert worker._status_code == 200
        web_resource = worker._web_resource
        assert web_resource is not None
        assert web_resource.url == "https://kramer.com/cigars.data"
        assert web_resource.sha256_hexdigest == "3b5bfeea08c04b2e1464b6469416b1378b7f83b7dc38377ff3cfd4ace93145e7"
        assert web_resource.encoding == "ISO-8859-1"
        assert web_resource.etag == "Kalahari"
        assert web_resource.content_url == "s3://fake-web-resource-bucket/del/boca/vista/webresource/cigars.data"
        assert web_resource.content is None
        assert web_resource.freshness.timestamp() == pytest.approx(utcnow().timestamp())

    def test_fetch_existing_url_content_didnt_change(self, responses) -> None:
        s3 = S3()
        self._add_response(responses, "https://jerry.com/pole.data", "The went like hotcakes")
        web_resource = WebResource.objects.create(
            url="https://jerry.com/pole.data",
            sha256_hexdigest="e113ffdce36886616d60d7762de35c0d10d96d80a6203a628a9a148d69d12e3a",
            freshness=datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc),
            encoding="",
            compression=WebResource.IDENTITY,
            content_url="summarine-captain",
            content=None,
            etag="pennypecker",
        )
        payload = FetchURL.get_or_create("https://jerry.com/pole.data")
        worker = URLFetcher()
        assert worker.do_work(payload) is True
        assert len(responses.calls) == 1
        request = responses.calls[0].request
        assert request.headers["If-None-Match"] == "pennypecker"
        assert WebResource.objects.count() == 1
        assert s3.exists(self._BUCKET, key="del/boca/vista/webresource/pole.data") is True
        content = s3.get_content(self._BUCKET, key="del/boca/vista/webresource/pole.data")
        assert content == b"The went like hotcakes"
        assert worker._content_changed is False
        assert worker._status_code == 200
        web_resource = worker._web_resource
        assert web_resource is not None
        assert web_resource.url == "https://jerry.com/pole.data"
        assert web_resource.sha256_hexdigest == "e113ffdce36886616d60d7762de35c0d10d96d80a6203a628a9a148d69d12e3a"
        assert web_resource.encoding == "ISO-8859-1"
        assert web_resource.etag == "Kalahari"
        assert web_resource.content_url == "summarine-captain"
        assert web_resource.content is None
        assert web_resource.freshness.timestamp() == pytest.approx(utcnow().timestamp())
        assert WebResource.objects.count() == 1

    def test_fetch_existing_url_identical_content(self, responses) -> None:
        responses.add(responses.GET, "https://kramer.com/cigars.doc", stream=True, body="wood jerry, wood", status=304)
        WebResource.objects.create(
            url="https://kramer.com/cigars.doc",
            sha256_hexdigest="Nexus of the universe",
            freshness=datetime.datetime(2020, 8, 22, 10, 22, 50, tzinfo=datetime.timezone.utc),
            encoding="",
            compression=WebResource.IDENTITY,
            content_url="s3://fake-web-resource-bucket/del/boca/vista/webresource/cigars.doc",
            content=None,
            etag="Chicken",
        )
        s3 = S3()
        payload = FetchURL.get_or_create("https://kramer.com/cigars.doc")
        worker = URLFetcher()
        assert worker.do_work(payload) is True
        assert len(responses.calls) == 1
        request = responses.calls[0].request
        assert request.headers["If-None-Match"] == "Chicken"
        assert WebResource.objects.count() == 1
        # Because content should already be there, so we don't re-upload
        assert s3.exists(self._BUCKET, key="del/boca/vista/webresource/cigars.doc") is False
        assert worker._status_code == 304
        web_resource = worker._web_resource
        assert web_resource is not None
        assert web_resource.url == "https://kramer.com/cigars.doc"
        assert web_resource.sha256_hexdigest == "Nexus of the universe"
        assert web_resource.encoding == ""
        assert web_resource.etag == "Chicken"
        assert web_resource.content_url == "s3://fake-web-resource-bucket/del/boca/vista/webresource/cigars.doc"
        assert web_resource.freshness.timestamp() == pytest.approx(utcnow().timestamp())

    def test_fetch_existing_url_connection_error(self, responses) -> None:
        responses.add(
            responses.GET, "https://kramer.com/cigars.doc", stream=True, body=ConnectionError("No socket for you")
        )
        payload = FetchURL.get_or_create("https://kramer.com/cigars.doc")
        worker = URLFetcher()
        with pytest.raises(
            TransientWorkException, match=re.escape("connection issue: ConnectionError('No socket for you')")
        ):
            worker.do_work(payload)
        assert worker._status_code is None
        assert len(responses.calls) == 1
        assert WebResource.objects.count() == 0
        assert_bucket_empty(S3(), self._BUCKET)
        assert worker._web_resource is None

    def test_fetch_url_http_transient_error(self, responses) -> None:
        responses.add(responses.GET, "https://kramer.com/cigars.txt", stream=True, status=502)
        payload = FetchURL.get_or_create("https://kramer.com/cigars.txt")
        worker = URLFetcher()
        with pytest.raises(TransientWorkException, match="Got HTTP status 502 fetching https://kramer.com/cigars.txt"):
            worker.do_work(payload)
        assert worker._status_code == 502
        assert len(responses.calls) == 1
        assert WebResource.objects.count() == 0
        assert_bucket_empty(S3(), self._BUCKET)
        assert worker._web_resource is None

    def test_fetch_url_http_permanent_error(self, responses) -> None:
        responses.add(responses.GET, "https://kramer.com/cigars.txt", stream=True, status=403)
        payload = FetchURL.get_or_create("https://kramer.com/cigars.txt")
        worker = URLFetcher()
        with pytest.raises(PermanentWorkException, match="Got HTTP status 403 fetching https://kramer.com/cigars.txt"):
            worker.do_work(payload)
        assert worker._status_code == 403
        assert len(responses.calls) == 1
        assert WebResource.objects.count() == 0
        assert_bucket_empty(S3(), self._BUCKET)
        assert worker._web_resource is None

    @pytest.mark.parametrize("last_status", [400, 503, 200, None])
    def test_fetch_url_not_found_first_time(self, responses, last_status) -> None:
        responses.add(responses.GET, "https://kramer.com/cigars.txt", stream=True, status=404)
        payload = FetchURL.get_or_create("https://kramer.com/cigars.txt")
        payload.last_http_status = last_status
        payload.save()
        worker = URLFetcher()
        with pytest.raises(TransientWorkException, match="Got HTTP status 404 fetching https://kramer.com/cigars.txt"):
            worker.do_work(payload)
        assert worker._status_code == 404
        assert len(responses.calls) == 1
        assert WebResource.objects.count() == 0
        assert_bucket_empty(S3(), self._BUCKET)
        assert worker._web_resource is None

    def test_fetch_url_not_found_consecutive(self, responses) -> None:
        responses.add(responses.GET, "https://kramer.com/cigars.txt", stream=True, status=404)
        payload = FetchURL.get_or_create("https://kramer.com/cigars.txt")
        payload.last_http_status = 404
        worker = URLFetcher()
        with pytest.raises(PermanentWorkException, match="Got HTTP status 404 fetching https://kramer.com/cigars.txt"):
            worker.do_work(payload)
        assert worker._status_code == 404
        assert len(responses.calls) == 1
        assert WebResource.objects.count() == 0
        assert_bucket_empty(S3(), self._BUCKET)
        assert worker._web_resource is None
