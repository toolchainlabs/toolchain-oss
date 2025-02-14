# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

import pytest
from moto import mock_s3

from toolchain.aws.s3 import S3
from toolchain.aws.test_utils.s3_utils import create_s3_bucket
from toolchain.base.datetime_tools import utcnow
from toolchain.crawler.base.models import FetchURL
from toolchain.crawler.pypi.workers.pypi_url_fetcher import PypiURLFetcher
from toolchain.django.webresource.models import WebResource
from toolchain.lang.python.test_helpers.utils import get_dist_binary_data
from toolchain.workflow.error import PermanentWorkException, TransientWorkException


@pytest.mark.django_db()
class TestPypiURLFetcher:
    _PYPY_URL = "https://files.pythonhosted.org/packages/1d/14/bb52426206469ad3acbc64d5ee753558d2598beb96386565789d4c02b424/ccxt-1.26.96-py2.py3-none-any.whl#sha256=f10a501c38326e114814c1af7a0b6bbc9bdeb7a5f014b96a6aff4a962252639f"

    @pytest.fixture(autouse=True)
    def _start_moto(self, settings):
        with mock_s3():
            create_s3_bucket(settings.WEBRESOURCE_BUCKET)
            yield

    def _read_dist(self) -> bytes:
        return get_dist_binary_data("requests-2.22.0.tar.gz")

    def _add_response(self, responses, body: bytes, headers: dict | None = None) -> None:
        adding_headers = {"Content-Length": str(len(body))}
        adding_headers.update(headers or {})
        responses.add(
            responses.GET,
            self._PYPY_URL,
            stream=True,
            body=body,
            content_type="application/octet-stream",
            adding_headers=adding_headers,
        )

    def _assert_saved_dist(self, content_url: str, dist_data: bytes) -> None:
        s3 = S3()
        s3.url_exists(content_url)
        bucket, key = s3.parse_s3_url(content_url)
        assert bucket == "jambalaya"
        assert s3.get_content(bucket="jambalaya", key=key) == dist_data

    def _assert_web_resource(self, webresource: WebResource, content_url: str | None = None) -> None:
        content_url = (
            content_url
            or "s3://jambalaya/seinfeld/no-soup-for-you/webresource/packages/1d/14/bb52426206469ad3acbc64d5ee753558d2598beb96386565789d4c02b424/ccxt-1.26.96-py2.py3-none-any.whl"
        )
        assert (
            webresource.url
            == "https://files.pythonhosted.org/packages/1d/14/bb52426206469ad3acbc64d5ee753558d2598beb96386565789d4c02b424/ccxt-1.26.96-py2.py3-none-any.whl#sha256=f10a501c38326e114814c1af7a0b6bbc9bdeb7a5f014b96a6aff4a962252639f"
        )
        assert webresource.sha256_hexdigest == "11e007a8a2aa0323f5a921e9e6a2d7e4e67d9877e85773fba9ba6419025cbeb4"
        assert webresource.freshness.timestamp() == pytest.approx(utcnow().timestamp())
        assert webresource.compression == "id"
        assert webresource.content is None
        assert webresource.content_url == content_url

    def test_fetch_pypi_resource_no_compression(self, responses) -> None:
        dist = self._read_dist()
        self._add_response(responses, dist)
        payload = FetchURL.get_or_create(self._PYPY_URL)
        assert WebResource.objects.count() == 0
        worker = PypiURLFetcher()
        assert worker.do_work(payload) is True
        assert WebResource.objects.count() == 0
        assert worker._status_code == 200
        assert worker._content_changed is True
        web_resource = worker._web_resource
        assert web_resource is not None
        self._assert_web_resource(web_resource)
        assert web_resource.etag == "Not Set"
        self._assert_saved_dist(web_resource.content_url, dist)
        assert len(responses.calls) == 1

    def test_fetch_pypi_resource_no_compression_with_etag(self, responses) -> None:
        dist = self._read_dist()
        self._add_response(responses, dist, headers={"ETAG": '"c70fcaa4abba16c1874c65a643e525f9"'})
        payload = FetchURL.get_or_create(self._PYPY_URL)
        assert WebResource.objects.count() == 0
        worker = PypiURLFetcher()
        assert worker.do_work(payload) is True
        assert WebResource.objects.count() == 0
        assert worker._status_code == 200
        assert worker._content_changed is True
        web_resource = worker._web_resource
        assert web_resource is not None
        self._assert_web_resource(web_resource)
        assert web_resource.etag == '"c70fcaa4abba16c1874c65a643e525f9"'
        self._assert_saved_dist(web_resource.content_url, dist)
        assert len(responses.calls) == 1

    def test_fetch_pypi_resource_transient_http_error(self, responses) -> None:
        responses.add(responses.GET, self._PYPY_URL, status=501)
        payload = FetchURL.get_or_create(self._PYPY_URL)
        worker = PypiURLFetcher()
        with pytest.raises(TransientWorkException, match=r"Got HTTP status 501 fetching https://files.*"):
            worker.do_work(payload)
        assert len(responses.calls) == 1
        assert worker._web_resource is None
        assert worker._status_code == 501
        assert worker._content_changed is True

    def test_fetch_pypi_resource_permanent_http_error(self, responses) -> None:
        responses.add(responses.GET, self._PYPY_URL, status=401)
        payload = FetchURL.get_or_create(self._PYPY_URL)
        worker = PypiURLFetcher()
        with pytest.raises(PermanentWorkException, match=r"Got HTTP status 401 fetching https://files.*"):
            worker.do_work(payload)
        assert len(responses.calls) == 1
        assert worker._web_resource is None
        assert worker._status_code == 401
        assert worker._content_changed is True

    def test_fetch_pypi_resource_exists_no_changes(self, responses) -> None:
        responses.add(responses.GET, self._PYPY_URL, status=304)
        payload = FetchURL.get_or_create(self._PYPY_URL)
        web_resource_id = WebResource.objects.create(
            url=payload.url,
            sha256_hexdigest="11e007a8a2aa0323f5a921e9e6a2d7e4e67d9877e85773fba9ba6419025cbeb4",
            freshness=utcnow() - datetime.timedelta(days=20),
            encoding="",
            compression=WebResource.IDENTITY,
            content_url="s3://no-soup-for-you",
            etag='"c70fcaa4abba16c1874c65a643e525f9"',
        ).id

        assert WebResource.objects.count() == 1
        worker = PypiURLFetcher()
        assert worker.do_work(payload) is True
        assert WebResource.objects.count() == 1
        assert worker._status_code == 304
        web_resource = worker._web_resource
        assert web_resource is not None
        assert web_resource == WebResource.objects.get(id=web_resource_id)
        self._assert_web_resource(web_resource, content_url="s3://no-soup-for-you")
        assert worker._content_changed is False

    def test_fetch_pypi_resource_exists_and_changed(self, responses) -> None:
        dist = self._read_dist()
        self._add_response(responses, dist, headers={"ETAG": '"c70fcaa4abba16c1874c65a643e525f9"'})
        payload = FetchURL.get_or_create(self._PYPY_URL)
        web_resource_id = WebResource.objects.create(
            url=payload.url,
            sha256_hexdigest="11e007a8a2aa0323f5a921e9e6a2d7e4e67d9877e85773fba9ba6419025cbeb4",
            freshness=utcnow() - datetime.timedelta(days=20),
            encoding="",
            compression=WebResource.IDENTITY,
            content_url="s3://no-soup-for-you/comeback-one-year.gz",
            etag="old-etag-value",
        ).id

        assert WebResource.objects.count() == 1
        worker = PypiURLFetcher()
        assert worker.do_work(payload) is True
        assert WebResource.objects.count() == 1
        assert worker._status_code == 200
        web_resource = worker._web_resource
        assert web_resource is not None
        assert worker._web_resource == WebResource.objects.get(id=web_resource_id)
        self._assert_web_resource(web_resource, content_url="s3://no-soup-for-you/comeback-one-year.gz")
        assert worker._content_changed is False

    def test_on_success(self):
        payload = FetchURL.get_or_create(self._PYPY_URL)
        dist = self._read_dist()
        S3().upload_content(
            bucket="jambalaya", key="/seinfeld/no-soup-for-you/requests-2.22.0-dist", content_bytes=dist
        )
        worker = PypiURLFetcher()
        worker._web_resource = WebResource(
            url=payload.url,
            sha256_hexdigest="11e007a8a2aa0323f5a921e9e6a2d7e4e67d9877e85773fba9ba6419025cbeb4",
            freshness=utcnow() - datetime.timedelta(minutes=90),
            encoding="",
            compression=WebResource.IDENTITY,
            content_url="s3://jambalaya/seinfeld/no-soup-for-you/requests-2.22.0-dist",
            etag='"c70fcaa4abba16c1874c65a643e525f9"',
        )
        worker._content_changed = True
        worker._status_code = 201
        assert WebResource.objects.count() == 0
        worker.on_success(payload)
        payload.save()
        assert FetchURL.objects.count() == 1
        assert WebResource.objects.count() == 1
        updated_payload = FetchURL.objects.first()
        assert updated_payload.last_http_status == 201
        assert updated_payload.web_resource_id == WebResource.objects.first().id
        assert updated_payload.web_resource == WebResource.objects.first()
