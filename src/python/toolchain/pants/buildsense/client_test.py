# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import zlib

import pytest
from pants.version import VERSION as PANTS_VERSION
from requests.exceptions import ConnectionError, ReadTimeout

from toolchain.buildsense.test_utils.fixtures_loader import load_fixture
from toolchain.pants.auth.client import AuthState
from toolchain.pants.auth.token import AuthToken
from toolchain.pants.buildsense.client import BuildSenseClient
from toolchain.pants.version import VERSION as TOOLCHAIN_VERSION
from toolchain.util.constants import REQUEST_ID_HEADER
from toolchain.util.test.multipart_parser import parse_multipart_request

_PANTS_VERSION_USER_AGENT_STR = f"pants/v{PANTS_VERSION} toolchain/v{TOOLCHAIN_VERSION}"


def _load_fixture(fixture: str):
    build_data = load_fixture(fixture)
    run_id = build_data["run_info"]["id"]
    return build_data, run_id


class FakeAuthStore:
    def __init__(self) -> None:
        self.token = AuthToken(
            access_token="funny-boy", expires_at=datetime.datetime(2028, 7, 9, tzinfo=datetime.timezone.utc)
        )

    def get_auth_state(self) -> AuthState:
        return AuthState.OK

    def get_access_token(self) -> AuthToken:
        return self.token


@pytest.fixture(params=[None, "seinfeld"])
def client(request) -> BuildSenseClient:
    return BuildSenseClient(
        base_url="http://localhost:8333/api/v1/repos/",
        repo="pudding",
        auth=FakeAuthStore(),  # type: ignore[arg-type]
        timeout=1,
        dry_run=False,
        org_name=request.param,
        batch_timeout=11,
    )


def _add_response(responses, method: str, client: BuildSenseClient, end_path, **kwargs):
    slug = "seinfeld/pudding" if client._org else "pudding"
    responses.add(method, f"http://localhost:8333/api/v1/repos/{slug}/buildsense/{end_path}", **kwargs)


def _assert_run_id_url(request, client: BuildSenseClient) -> None:
    if client._org:
        assert (
            request.url
            == "http://localhost:8333/api/v1/repos/seinfeld/pudding/buildsense/pants_run_2020_01_23_11_41_55_931_68189fba67f94d7ebd9b119f4966124c/"
        )
    else:
        assert (
            request.url
            == "http://localhost:8333/api/v1/repos/pudding/buildsense/pants_run_2020_01_23_11_41_55_931_68189fba67f94d7ebd9b119f4966124c/"
        )


def test_submit_run_end(responses, client: BuildSenseClient) -> None:
    build_stats, run_id = _load_fixture("sample_9_end")
    _add_response(responses, responses.PATCH, client, f"{run_id}/", json={})
    client.submit_run_end(run_id=run_id, user_api_id="tinsel", build_stats=build_stats)
    assert len(responses.calls) == 1
    request = responses.calls[0].request
    _assert_run_id_url(request, client)
    assert _parse_json_file(request) == build_stats
    assert request.method == "PATCH"
    assert request.headers["User-Agent"] == _PANTS_VERSION_USER_AGENT_STR
    assert request.headers["Authorization"] == "Bearer funny-boy"
    assert request.headers["Content-Type"].startswith("multipart/form-data; boundary=")
    assert request.headers["X-Toolchain-Impersonate"] == "tinsel"


def test_submit_run_end_compressed(responses, client) -> None:
    client._compression_threshold = 10
    client._successful_calls = 2
    assert client.has_successful_calls is False
    build_stats, run_id = _load_fixture("sample_9_end")
    _add_response(responses, responses.PATCH, client, f"{run_id}/", json={"created": True})
    run_end_info = client.submit_run_end(run_id=run_id, user_api_id="tinsel", build_stats=build_stats)
    assert run_end_info.success is True
    assert len(responses.calls) == 1
    request = responses.calls[0].request
    _assert_run_id_url(request, client)
    assert build_stats == _parse_json_file(request, decompress=True)
    assert request.method == "PATCH"
    assert request.headers["User-Agent"] == _PANTS_VERSION_USER_AGENT_STR
    assert request.headers["Authorization"] == "Bearer funny-boy"
    assert request.headers["Content-Encoding"] == "compress"
    assert request.headers["X-Toolchain-Impersonate"] == "tinsel"
    assert client.has_successful_calls is True


def test_submit_run_end_http_fail(responses, client) -> None:
    build_stats, run_id = _load_fixture("sample_9_end")
    client._successful_calls = 30
    assert client.has_successful_calls is True
    _add_response(
        responses, responses.PATCH, client, f"{run_id}/", status=503, adding_headers={REQUEST_ID_HEADER: "pez"}
    )
    run_end_info = client.submit_run_end(run_id=run_id, user_api_id=None, build_stats=build_stats)
    assert run_end_info.success is False
    assert run_end_info.data is not None
    assert len(run_end_info.data) == 6596
    assert len(responses.calls) == 1
    request = responses.calls[0].request
    _assert_run_id_url(request, client)
    assert request.method == "PATCH"
    assert request.headers["User-Agent"] == _PANTS_VERSION_USER_AGENT_STR
    assert request.headers["Authorization"] == "Bearer funny-boy"
    assert "Content-Encoding" not in request.headers
    assert "X-Toolchain-Impersonate" not in request.headers
    assert client.has_successful_calls is False


def _assert_run_start_request(request, client) -> dict:
    _assert_run_id_url(request, client)
    assert request.method == "POST"
    assert request.headers["User-Agent"] == _PANTS_VERSION_USER_AGENT_STR
    assert request.headers["Authorization"] == "Bearer funny-boy"
    assert request.headers["Content-Type"].startswith("multipart/form-data; boundary=")
    assert "X-Toolchain-Impersonate" not in request.headers
    return _parse_json_file(request)


def test_submit_run_start(responses, client: BuildSenseClient) -> None:
    build_stats, run_id = _load_fixture("sample_9_start")
    _add_response(responses, responses.POST, client, f"{run_id}/", json={"link": "https://jerry.seinfeld/soup"})
    run_info = client.submit_run_start(run_id=run_id, build_stats=build_stats)
    assert run_info is not None
    assert run_info.ci_user_api_id is None
    assert run_info.build_link == "https://jerry.seinfeld/soup"
    assert len(responses.calls) == 1
    request = responses.calls[0].request
    assert _assert_run_start_request(request, client) == build_stats
    assert client.has_successful_calls is False


def test_submit_run_start_with_user_api_id(responses, client: BuildSenseClient) -> None:
    build_stats, run_id = _load_fixture("sample_9_start")
    _add_response(
        responses,
        responses.POST,
        client,
        f"{run_id}/",
        json={"ci_user_api_id": "pole", "link": "https://jerry.seinfeld/soup"},
    )
    client._successful_calls = 2
    assert client.has_successful_calls is False
    run_info = client.submit_run_start(run_id=run_id, build_stats=build_stats)
    assert run_info is not None
    assert run_info.ci_user_api_id == "pole"
    assert run_info.build_link == "https://jerry.seinfeld/soup"
    assert len(responses.calls) == 1
    request = responses.calls[0].request
    assert _assert_run_start_request(request, client) == build_stats
    assert client.has_successful_calls is True


def test_submit_run_start_http_error(responses, client: BuildSenseClient) -> None:
    build_stats, run_id = _load_fixture("sample_9_start")
    _add_response(responses, responses.POST, client, f"{run_id}/", status=500)
    client._successful_calls = 30
    assert client.has_successful_calls is True
    run_info = client.submit_run_start(run_id=run_id, build_stats=build_stats)
    assert run_info is None
    assert len(responses.calls) == 1
    request = responses.calls[0].request
    assert _assert_run_start_request(request, client) == build_stats
    assert client.has_successful_calls is False


def test_submit_run_start_network_error(responses, client: BuildSenseClient) -> None:
    build_stats, run_id = _load_fixture("sample_9_start")
    _add_response(
        responses,
        responses.POST,
        client,
        f"{run_id}/",
        body=ReadTimeout("George isn't at home"),
    )
    run_info = client.submit_run_start(run_id=run_id, build_stats=build_stats)
    assert run_info is None
    assert len(responses.calls) == 1
    request = responses.calls[0].request
    assert _assert_run_start_request(request, client) == build_stats
    assert client.has_successful_calls is False


def test_submit_batch(responses, client: BuildSenseClient) -> None:
    client._successful_calls = 2
    assert client.has_successful_calls is False
    build_stats, _ = _load_fixture("sample_9_start")
    _add_response(responses, responses.POST, client, "batch/", json="OK")
    client.submit_batch(batched_data=json.dumps(build_stats), batch_name="jerry", user_api_id=None)
    assert len(responses.calls) == 1
    request = responses.calls[0].request
    if client._org:
        assert request.url == "http://localhost:8333/api/v1/repos/seinfeld/pudding/buildsense/batch/"
    else:
        assert request.url == "http://localhost:8333/api/v1/repos/pudding/buildsense/batch/"
    assert _parse_json_file(request) == build_stats
    assert request.method == "POST"
    assert request.headers["User-Agent"] == _PANTS_VERSION_USER_AGENT_STR
    assert request.headers["Authorization"] == "Bearer funny-boy"
    assert request.headers["Content-Type"].startswith("multipart/form-data; boundary=")
    assert "X-Toolchain-Impersonate" not in request.headers
    assert client.has_successful_calls is True


def test_submit_workunits(responses, client: BuildSenseClient) -> None:
    client._successful_calls = 2
    assert client.has_successful_calls is False
    build_stats, _ = _load_fixture("sample_9_start")
    _add_response(responses, responses.POST, client, "pez/workunits/", json={"result": "ok"})
    client.submit_workunits(run_id="pez", call_num=3, user_api_id="davola", workunits=[{"soup": "no soup for you"}])
    assert len(responses.calls) == 1
    request = responses.calls[0].request
    if client._org:
        assert request.url == "http://localhost:8333/api/v1/repos/seinfeld/pudding/buildsense/pez/workunits/"
    else:
        assert request.url == "http://localhost:8333/api/v1/repos/pudding/buildsense/pez/workunits/"
    assert _parse_json_file(request) == {"workunits": [{"soup": "no soup for you"}], "run_id": "pez"}
    assert request.method == "POST"
    assert request.headers["User-Agent"] == _PANTS_VERSION_USER_AGENT_STR
    assert request.headers["Authorization"] == "Bearer funny-boy"
    assert request.headers["Content-Type"].startswith("multipart/form-data; boundary=")
    assert request.headers["X-Toolchain-Impersonate"] == "davola"
    assert client.has_successful_calls is True


def test_upload_artifacts(responses, client: BuildSenseClient) -> None:
    client._successful_calls = 2
    _add_response(responses, responses.POST, client, "support_the_team/artifacts/", json="OK")
    artifacts = {"coverage.bin": b"look to the cookie." * 300}
    success = client.upload_artifacts(run_id="support_the_team", artifacts=artifacts, user_api_id=None)
    assert success is True
    assert len(responses.calls) == 1
    request = responses.calls[0].request
    if client._org:
        assert (
            request.url == "http://localhost:8333/api/v1/repos/seinfeld/pudding/buildsense/support_the_team/artifacts/"
        )
    else:
        assert request.url == "http://localhost:8333/api/v1/repos/pudding/buildsense/support_the_team/artifacts/"

    assert request.method == "POST"
    assert request.headers["User-Agent"] == _PANTS_VERSION_USER_AGENT_STR
    assert request.headers["Authorization"] == "Bearer funny-boy"
    assert "X-Toolchain-Impersonate" not in request.headers
    data = _parse_file(request, "coverage.bin")
    assert zlib.decompress(data) == b"look to the cookie." * 300
    assert client.has_successful_calls is True


def test_upload_artifacts_network_error(responses, client: BuildSenseClient) -> None:
    client._successful_calls = 10
    _add_response(responses, responses.POST, client, "8ball/artifacts/", body=ConnectionError("Feats of strength"))
    artifacts = {"coverage.bin": b"look to the cookie." * 300}
    success = client.upload_artifacts(run_id="8ball", artifacts=artifacts, user_api_id="jambalaya")
    assert success is False
    assert len(responses.calls) == 1
    request = responses.calls[0].request
    if client._org:
        assert request.url == "http://localhost:8333/api/v1/repos/seinfeld/pudding/buildsense/8ball/artifacts/"
    else:
        assert request.url == "http://localhost:8333/api/v1/repos/pudding/buildsense/8ball/artifacts/"

    assert request.method == "POST"
    assert request.headers["User-Agent"] == _PANTS_VERSION_USER_AGENT_STR
    assert request.headers["Authorization"] == "Bearer funny-boy"
    assert request.headers["X-Toolchain-Impersonate"] == "jambalaya"
    data = _parse_file(request, "coverage.bin")
    assert zlib.decompress(data) == b"look to the cookie." * 300
    assert client.has_successful_calls is False


def test_upload_artifacts_http_error(responses, client: BuildSenseClient) -> None:
    client._successful_calls = 8
    _add_response(responses, responses.POST, client, "8ball/artifacts/", status=502)
    artifacts = {"coverage.bin": b"look to the cookie." * 300}
    success = client.upload_artifacts(run_id="8ball", artifacts=artifacts, user_api_id="jambalaya")
    assert success is False
    assert len(responses.calls) == 1
    request = responses.calls[0].request
    if client._org:
        assert request.url == "http://localhost:8333/api/v1/repos/seinfeld/pudding/buildsense/8ball/artifacts/"
    else:
        assert request.url == "http://localhost:8333/api/v1/repos/pudding/buildsense/8ball/artifacts/"

    assert request.method == "POST"
    assert request.headers["User-Agent"] == _PANTS_VERSION_USER_AGENT_STR
    assert request.headers["Authorization"] == "Bearer funny-boy"
    assert request.headers["X-Toolchain-Impersonate"] == "jambalaya"
    data = _parse_file(request, "coverage.bin")
    assert zlib.decompress(data) == b"look to the cookie." * 300
    assert client.has_successful_calls is False


def test_submit_run_end_no_token(client) -> None:
    build_stats, run_id = _load_fixture("sample_9_end")
    client._auth.token = AuthToken.no_token()
    run_end_info = client.submit_run_end(run_id=run_id, user_api_id="tinsel", build_stats=build_stats)
    assert run_end_info.success is False
    assert client.has_successful_calls is False


def test_get_plugin_config(responses, client: BuildSenseClient) -> None:
    _add_response(responses, responses.OPTIONS, client, "", json={"config": {"workunits": "from the institute"}})
    config = client.get_plugin_config()
    assert config == {"config": {"workunits": "from the institute"}}
    assert len(responses.calls) == 1
    request = responses.calls[0].request
    if client._org:
        assert request.url == "http://localhost:8333/api/v1/repos/seinfeld/pudding/buildsense/"
    else:
        assert request.url == "http://localhost:8333/api/v1/repos/pudding/buildsense/"
    assert request.method == "OPTIONS"
    assert request.headers["User-Agent"] == _PANTS_VERSION_USER_AGENT_STR
    assert request.headers["Authorization"] == "Bearer funny-boy"
    assert client.has_successful_calls is False


def test_get_plugin_config_http_error(responses, client: BuildSenseClient) -> None:
    _add_response(responses, responses.OPTIONS, client, "", status=500)
    config = client.get_plugin_config()
    assert config is None
    assert len(responses.calls) == 1
    request = responses.calls[0].request
    if client._org:
        assert request.url == "http://localhost:8333/api/v1/repos/seinfeld/pudding/buildsense/"
    else:
        assert request.url == "http://localhost:8333/api/v1/repos/pudding/buildsense/"
    assert request.method == "OPTIONS"
    assert request.headers["User-Agent"] == _PANTS_VERSION_USER_AGENT_STR
    assert request.headers["Authorization"] == "Bearer funny-boy"
    assert client.has_successful_calls is False


def test_get_plugin_config_network_error(responses, client: BuildSenseClient) -> None:
    _add_response(responses, responses.OPTIONS, client, "", body=ConnectionError("Feats of strength"))

    config = client.get_plugin_config()
    assert config is None
    assert len(responses.calls) == 1
    request = responses.calls[0].request
    if client._org:
        assert request.url == "http://localhost:8333/api/v1/repos/seinfeld/pudding/buildsense/"
    else:
        assert request.url == "http://localhost:8333/api/v1/repos/pudding/buildsense/"
    assert request.method == "OPTIONS"
    assert request.headers["User-Agent"] == _PANTS_VERSION_USER_AGENT_STR
    assert request.headers["Authorization"] == "Bearer funny-boy"
    assert client.has_successful_calls is False


def _parse_file(request, filename: str) -> bytes:
    _, files = parse_multipart_request(request)
    return files[filename].raw


def _parse_json_file(request, decompress: bool = False) -> dict:
    data = _parse_file(request, "buildsense")
    return json.loads(zlib.decompress(data) if decompress else data)
