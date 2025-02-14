# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from unittest import mock

import httpx
import ndjson
import pytest

from toolchain.aws.dynamodb import ValuesConverter
from toolchain.base.datetime_tools import utcnow
from toolchain.buildsense.dynamodb_es_bridge.dynamodb_to_es_lambda import BuildDataDynamoDB2ElasticSearch
from toolchain.buildsense.records.run_info import RunInfo, ServerInfo
from toolchain.buildsense.search.es_config import BuildSenseElasticSearchConfig
from toolchain.buildsense.test_utils.data_loader import parse_run_info
from toolchain.buildsense.test_utils.fixtures_loader import load_fixture
from toolchain.util.test.elastic_search_util import DummyElasticRequests
from toolchain.util.test.util import assert_messages

_REMOVE_RECORD = {
    "eventName": "REMOVE",
    "dynamodb": {"Keys": {"EnvCustomerRepoUser": {"S": "crab bisque"}, "run_id": {"S": "golden boy"}}},
}


def _get_dynamo_json_for_run_info(run_info: RunInfo, drop_title: bool) -> dict:
    record = run_info.to_json_dict()
    if drop_title:
        del record["title"]  # simulate title field not being in dynamodb data
    del record["timestamp"]
    record.update({"EnvCustomerRepoUser": "", "EnvCustomerRepo": "", "Environment": "", "run_timestamp": 44444})
    return ValuesConverter().convert_item(record)


def _get_record_for_fixture(fixture: str, drop_title: bool) -> dict:
    fixture_data = load_fixture(fixture)
    mock_user = mock.MagicMock(api_id="newman")
    dummy_server_info = ServerInfo(
        request_id="The Human Fund: Money For People",
        accept_time=utcnow(),
        stats_version="1",
        environment="crab/bisque",
        s3_bucket="fake-bucket",
        s3_key="fake-key",
    )
    mock_repo = mock.MagicMock(pk="babka", customer_id="giddyup")
    run_info = parse_run_info(fixture_data=fixture_data, repo=mock_repo, user=mock_user, server_info=dummy_server_info)
    return _get_dynamo_json_for_run_info(run_info, drop_title=drop_title)


@pytest.fixture(params=[True, False])
def input_records(request) -> list[dict]:
    update_run_info = _get_record_for_fixture("sample6", drop_title=request.param)
    update_record = {
        "eventName": "UPDATE",
        "dynamodb": {
            "NewImage": update_run_info,
            "Keys": {"EnvCustomerRepoUser": {"S": "babka"}, "run_id": {"S": "festivus"}},
        },
    }
    return [_REMOVE_RECORD, update_record]


@pytest.fixture(params=[True, False])
def input_records_with_ci_info(request) -> list[dict]:
    update_record_1 = {
        "eventName": "UPDATE",
        "dynamodb": {
            "NewImage": _get_record_for_fixture("sample6", drop_title=request.param),
            "Keys": {"EnvCustomerRepoUser": {"S": "babka"}, "run_id": {"S": "festivus"}},
        },
    }

    update_record_2 = {
        "eventName": "UPDATE",
        "dynamodb": {
            "NewImage": _get_record_for_fixture("ci_build_pr_final_1", drop_title=request.param),
            "Keys": {"EnvCustomerRepoUser": {"S": "babka"}, "run_id": {"S": "tinsel"}},
        },
    }
    return [_REMOVE_RECORD, update_record_2, update_record_1]


@pytest.fixture()
def pusher() -> BuildDataDynamoDB2ElasticSearch:
    cfg = BuildSenseElasticSearchConfig.for_tests(DummyElasticRequests.factory)
    return BuildDataDynamoDB2ElasticSearch("narnia", cfg)


def test_bulk_update_with_ci_info(
    httpx_mock, pusher: BuildDataDynamoDB2ElasticSearch, input_records_with_ci_info: list[dict]
) -> None:
    httpx_mock.add_response(
        method="POST", url="https://ovaltine.search.local/_bulk", json={"took": "2sec", "errors": 0, "items": [1, 2, 3]}
    )
    # Sanity checks on fixture data, since this test also validated that we drop this field (target_data) from
    # the data we push to ES.
    action_count, http_code, resp_json = pusher.bulk_process_records(input_records_with_ci_info)
    assert action_count == 5
    request = httpx_mock.get_request()
    assert request.url == "https://ovaltine.search.local/_bulk"
    assert request.headers["Content-Type"] == "application/x-ndjson"
    docs_json = ndjson.loads(request.read())
    assert len(docs_json) == 5
    assert docs_json[0] == {"delete": {"_index": "buildsense-v2", "_id": "crab bisque:golden boy"}}
    assert docs_json[1] == {"index": {"_index": "buildsense-v2", "_id": "babka:tinsel"}}
    assert docs_json[3] == {"index": {"_index": "buildsense-v2", "_id": "babka:festivus"}}
    run_info_doc = docs_json[2]
    assert set(run_info_doc.keys()) == {
        "run_time",
        "specs_from_command_line",
        "title",
        "run_id",
        "buildroot",
        "revision",
        "repo_id",
        "machine",
        "version",
        "cmd_line",
        "timestamp",
        "user_api_id",
        "ci_info",
        "outcome",
        "computed_goals",
        "server_info",
        "customer_id",
        "path",
        "branch",
    }
    assert run_info_doc["timestamp"] == 44444.0
    assert "target_data" not in run_info_doc
    assert run_info_doc["cmd_line"] == "pants --pants-bin-name=./pants validate prod/python:: src/python::"
    assert run_info_doc["revision"] == "c5454b4327903b7d2242f705e9218ca90bcc7e49"
    assert run_info_doc["outcome"] == "SUCCESS"
    assert run_info_doc["run_id"] == "pants_run_2020_08_13_00_21_00_240_87ceaef8db824ad9ac25fa866e988427"
    assert run_info_doc["branch"] == "pull/6490"
    assert run_info_doc["run_time"] is None
    assert run_info_doc["ci_info"] == {
        "build_num": 22579.0,
        "build_url": "https://circleci.com/gh/toolchainlabs/toolchain/22579",
        "job_name": "build",
        "pull_request": 6490.0,
        "run_type": "pull_request",
        "username": "asherf",
        "link": None,
        "ref_name": "pull/6490",
    }


def test_bulk_update_with_ci_info_and_ci_link(
    httpx_mock, pusher: BuildDataDynamoDB2ElasticSearch, input_records_with_ci_info: list[dict]
) -> None:
    httpx_mock.add_response(
        method="POST", url="https://ovaltine.search.local/_bulk", json={"took": "2sec", "errors": 0, "items": [1, 2, 3]}
    )
    # Sanity checks on fixture data, since this test also validated that we drop this field (target_data) from
    # the data we push to ES.
    input_records_with_ci_info[1]["dynamodb"]["NewImage"]["ci_info"]["M"]["link"] = {
        "S": "https://puffy.shirt.com/pirate"
    }
    action_count, http_code, resp_json = pusher.bulk_process_records(input_records_with_ci_info)
    assert action_count == 5
    request = httpx_mock.get_request()
    assert request.url == "https://ovaltine.search.local/_bulk"
    assert request.headers["Content-Type"] == "application/x-ndjson"
    docs_json = ndjson.loads(request.read())
    assert len(docs_json) == 5
    assert docs_json[0] == {"delete": {"_index": "buildsense-v2", "_id": "crab bisque:golden boy"}}
    assert docs_json[1] == {"index": {"_index": "buildsense-v2", "_id": "babka:tinsel"}}
    assert docs_json[3] == {"index": {"_index": "buildsense-v2", "_id": "babka:festivus"}}
    run_info_doc = docs_json[2]
    assert set(run_info_doc.keys()) == {
        "run_time",
        "specs_from_command_line",
        "title",
        "run_id",
        "buildroot",
        "revision",
        "repo_id",
        "machine",
        "version",
        "cmd_line",
        "timestamp",
        "user_api_id",
        "ci_info",
        "outcome",
        "computed_goals",
        "server_info",
        "customer_id",
        "path",
        "branch",
    }
    assert run_info_doc["timestamp"] == 44444.0
    assert "target_data" not in run_info_doc
    assert run_info_doc["cmd_line"] == "pants --pants-bin-name=./pants validate prod/python:: src/python::"
    assert run_info_doc["revision"] == "c5454b4327903b7d2242f705e9218ca90bcc7e49"
    assert run_info_doc["outcome"] == "SUCCESS"
    assert run_info_doc["run_id"] == "pants_run_2020_08_13_00_21_00_240_87ceaef8db824ad9ac25fa866e988427"
    assert run_info_doc["branch"] == "pull/6490"
    assert run_info_doc["run_time"] is None
    assert run_info_doc["ci_info"] == {
        "build_num": 22579.0,
        "build_url": "https://circleci.com/gh/toolchainlabs/toolchain/22579",
        "job_name": "build",
        "pull_request": 6490.0,
        "run_type": "pull_request",
        "username": "asherf",
        "link": "https://puffy.shirt.com/pirate",
        "ref_name": "pull/6490",
    }


def test_bulk_update(httpx_mock, pusher: BuildDataDynamoDB2ElasticSearch, input_records: list[dict]) -> None:
    httpx_mock.add_response(
        method="POST", url="https://ovaltine.search.local/_bulk", json={"took": "2sec", "errors": 0, "items": [1, 2, 3]}
    )
    # Sanity checks on fixture data, since this test also validated that we drop this field (target_data) from
    # the data we push to ES.
    assert "target_data" not in input_records[1]["dynamodb"]["NewImage"]
    action_count, http_code, resp_json = pusher.bulk_process_records(input_records)
    assert action_count == 3
    assert http_code == 200
    assert resp_json == {"took": "2sec", "errors": 0, "items": [1, 2, 3]}
    request = httpx_mock.get_request()
    assert request.url == "https://ovaltine.search.local/_bulk"
    assert request.headers["Content-Type"] == "application/x-ndjson"
    docs_json = ndjson.loads(request.read())
    assert len(docs_json) == 3
    assert docs_json[0] == {"delete": {"_index": "buildsense-v2", "_id": "crab bisque:golden boy"}}
    assert docs_json[1] == {"index": {"_index": "buildsense-v2", "_id": "babka:festivus"}}
    run_info_doc = docs_json[2]
    assert set(run_info_doc.keys()) == {
        "run_time",
        "specs_from_command_line",
        "title",
        "run_id",
        "buildroot",
        "revision",
        "repo_id",
        "machine",
        "version",
        "cmd_line",
        "timestamp",
        "user_api_id",
        "ci_info",
        "outcome",
        "computed_goals",
        "server_info",
        "customer_id",
        "path",
        "branch",
    }
    assert run_info_doc["timestamp"] == 44444.0
    assert "target_data" not in run_info_doc
    assert run_info_doc["cmd_line"] == "pants --no-verify-config test src/python/toolchain/buildstats/ingestion/::"
    assert run_info_doc["revision"] == "fbe46bb57cebf1270481bdc83935eb5e2198037b"
    assert run_info_doc["outcome"] == "FAILURE"
    assert run_info_doc["run_id"] == "pants_run_2019_07_23_13_27_04_206_2849042e04974d23a1750dc5a290955a"
    assert run_info_doc["branch"] == "helen"
    assert run_info_doc["run_time"] is None
    assert run_info_doc["ci_info"] is None


def test_bulk_update_with_unknown_field(httpx_mock, pusher: BuildDataDynamoDB2ElasticSearch) -> None:
    data = _get_record_for_fixture("buildkite_github_pull_request_lint_run", drop_title=False)
    # Unknown fields
    data.update({"frank": {"S": "costanza"}, "george": {"L": [{"S": "dingo"}]}})
    update_record = {
        "eventName": "UPDATE",
        "dynamodb": {
            "NewImage": data,
            "Keys": {"EnvCustomerRepoUser": {"S": "babka"}, "run_id": {"S": "festivus"}},
        },
    }
    httpx_mock.add_response(
        method="POST", url="https://ovaltine.search.local/_bulk", json={"took": "2sec", "errors": 0, "items": [82]}
    )
    action_count, http_code, resp_json = pusher.bulk_process_records([update_record])
    assert action_count == 2
    request = httpx_mock.get_request()
    assert request.url == "https://ovaltine.search.local/_bulk"
    assert request.headers["Content-Type"] == "application/x-ndjson"
    docs_json = ndjson.loads(request.read())
    assert len(docs_json) == 2
    assert docs_json[0] == {"index": {"_index": "buildsense-v2", "_id": "babka:festivus"}}
    run_info_doc = docs_json[1]
    assert set(run_info_doc.keys()) == {
        "run_time",
        "specs_from_command_line",
        "title",
        "run_id",
        "buildroot",
        "revision",
        "repo_id",
        "machine",
        "version",
        "cmd_line",
        "timestamp",
        "user_api_id",
        "ci_info",
        "outcome",
        "computed_goals",
        "server_info",
        "customer_id",
        "path",
        "branch",
    }
    assert run_info_doc["timestamp"] == 44444.0
    assert "target_data" not in run_info_doc
    assert run_info_doc["cmd_line"] == "pants --pants-bin-name=./pants --pants-version=2.7.0rc4 lint ::"
    assert run_info_doc["revision"] == "b3635292e22d7bf19998e9cacf3d31ed4d86c77d"
    assert run_info_doc["outcome"] == "SUCCESS"
    assert run_info_doc["run_id"] == "pants_run_2021_09_21_23_06_22_418_68990434198f4bd5b5f8e0aad82d532d"
    assert run_info_doc["branch"] == "b3635292e22d7bf19998e9cacf3d31ed4d86c77d"
    assert run_info_doc["run_time"] is None


def test_bulk_update_failure(httpx_mock, pusher: BuildDataDynamoDB2ElasticSearch, input_records: list[dict]) -> None:
    httpx_mock.add_response(method="POST", url="https://ovaltine.search.local/_bulk", status_code=403)
    with pytest.raises(httpx.HTTPError):
        pusher.bulk_process_records(input_records)


def test_check_es_connection(httpx_mock, pusher: BuildDataDynamoDB2ElasticSearch) -> None:
    httpx_mock.add_response(method="GET", url="https://ovaltine.search.local/", json={"hello": "jerry"})
    response = pusher.check_es_connection()
    assert response == '{"hello": "jerry"}'


def test_check_es_connection_http_failure(httpx_mock, pusher: BuildDataDynamoDB2ElasticSearch) -> None:
    httpx_mock.add_response(method="GET", url="https://ovaltine.search.local/", status_code=403)
    with pytest.raises(httpx.HTTPError):
        pusher.check_es_connection()


def test_bulk_update_network_error(
    httpx_mock, pusher: BuildDataDynamoDB2ElasticSearch, input_records: list[dict], caplog
) -> None:
    httpx_mock.add_exception(
        httpx.ReadTimeout("no soup for you"), method="POST", url="https://ovaltine.search.local/_bulk"
    )
    with pytest.raises(httpx.ReadTimeout, match="no soup for you"):
        pusher.bulk_process_records(input_records)
    assert_messages(caplog, "Request Network error error. latency=")
