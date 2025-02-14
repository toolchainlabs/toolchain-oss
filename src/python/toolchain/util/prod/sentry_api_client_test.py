# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest
from freezegun import freeze_time

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.util.prod.sentry_api_client import SentryApiClient


class TestSentryApiClient:
    def add_response(self, httpx_mock, method: str, path: str):
        httpx_mock.add_response(
            method=method, url=f"https://sentry.io/api/0/organizations/jerry/{path}", json={"result": "ok"}
        )

    def add_list_releases_response(self, httpx_mock, release_count: int):
        releases_json = [{"version": f"release_{i}", "status": "open"} for i in range(release_count)]
        httpx_mock.add_response(
            method="GET", url="https://sentry.io/api/0/organizations/jerry/releases/?query=baby", json=releases_json
        )

    @pytest.fixture()
    def sentry_client(self) -> SentryApiClient:
        return SentryApiClient(api_key="costanza", organization_slug="jerry", project="frank")

    def _assert_auth(self, request) -> None:
        assert request.headers["Authorization"] == "Bearer costanza"

    @freeze_time(datetime.datetime(2022, 1, 1, 9, 12, tzinfo=datetime.timezone.utc))
    def test_create_release(self, httpx_mock, sentry_client: SentryApiClient) -> None:
        self.add_response(httpx_mock, method="POST", path="releases/")
        sentry_client.create_release(project_slug="seinfeld", release_name="festivus", commit_sha="denim-vest")
        request = httpx_mock.get_request()
        self._assert_auth(request)
        assert json.loads(request.read()) == {
            "version": "festivus",
            "ref": "denim-vest",
            "projects": ["seinfeld"],
            "date_released": None,
            "date_started": "2022-01-01T09:12:00+00:00",
        }

    @freeze_time(datetime.datetime(2022, 1, 3, 18, 12, tzinfo=datetime.timezone.utc))
    def test_update_release(self, httpx_mock, sentry_client: SentryApiClient) -> None:
        self.add_response(httpx_mock, method="PUT", path="releases/festivus/")
        sentry_client.update_release(project_slug="seinfeld", release_name="festivus")
        request = httpx_mock.get_request()
        self._assert_auth(request)
        assert json.loads(request.read()) == {
            "projects": ["seinfeld"],
            "date_released": "2022-01-03T18:12:00+00:00",
        }

    def _prep_files(self, base_path: Path) -> tuple[Path, ...]:
        base_path.mkdir(parents=True)
        fp_1 = base_path / "mulva.json"
        fp_1.write_text("Dolores")
        fp_2 = base_path / "pony.json"
        fp_2.write_text("The Pony Remark")
        return fp_1, fp_2

    def test_upload_release_files(self, httpx_mock, sentry_client: SentryApiClient, tmp_path: Path) -> None:
        self.add_response(httpx_mock, method="POST", path="releases/baby/files/")
        dist_dir = tmp_path / "jerry" / "seinfeld"
        sentry_client.upload_release_files(
            release_name="baby",
            file_paths=self._prep_files(dist_dir),
            base_local_dir=dist_dir,
            base_version_path="festivus/pole",
        )
        requests = httpx_mock.get_requests()
        assert len(requests) == 2
        for req in requests:
            self._assert_auth(req)
            assert req.headers["Content-Type"].startswith("multipart/form-data; boundary=")
        assert b"Dolores" in requests[0].read()
        assert b"The Pony Remark" in requests[1].read()

    def test_upload_js_release_files(self, httpx_mock, sentry_client: SentryApiClient, tmp_path: Path) -> None:
        self.add_response(httpx_mock, method="POST", path="releases/")
        self.add_response(httpx_mock, method="POST", path="releases/baby/files/")
        self.add_response(httpx_mock, method="PUT", path="releases/baby/")
        self.add_list_releases_response(httpx_mock, release_count=0)
        dist_dir = tmp_path / "jerry" / "seinfeld"
        sentry_client.upload_js_release_files(
            release_name="baby",
            commit_sha="puddy",
            release_files=self._prep_files(dist_dir),
            base_local_dir=dist_dir,
            base_version_path="festivus",
        )
        requests = httpx_mock.get_requests()
        assert len(requests) == 5

    def test_upload_js_release_files_release_exists(
        self, httpx_mock, sentry_client: SentryApiClient, tmp_path: Path
    ) -> None:
        self.add_list_releases_response(httpx_mock, release_count=1)
        dist_dir = tmp_path / "jerry" / "seinfeld"
        sentry_client.upload_js_release_files(
            release_name="baby",
            commit_sha="puddy",
            release_files=self._prep_files(dist_dir),
            base_local_dir=dist_dir,
            base_version_path="festivus",
        )
        requests = httpx_mock.get_requests()
        assert len(requests) == 1

    def test_upload_js_release_files_empty(self, sentry_client: SentryApiClient) -> None:
        with pytest.raises(ToolchainAssertion, match="No release files provided"):
            sentry_client.upload_js_release_files(
                release_name="baby",
                commit_sha="puddy",
                release_files=[],
                base_local_dir=Path("dist/"),
                base_version_path="soup",
            )
