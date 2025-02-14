# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import uuid

import boto3
import pytest
from moto import mock_dynamodb, mock_s3

from toolchain.aws.test_utils.s3_utils import create_s3_bucket
from toolchain.base.datetime_tools import utcnow
from toolchain.buildsense.build_data_queries import BuildsQueries
from toolchain.buildsense.ingestion.pants_data_ingestion import PantsDataIngestion
from toolchain.buildsense.ingestion.run_info_raw_store import RunInfoRawStore, WriteMode
from toolchain.buildsense.ingestion.run_info_table import RunInfoTable
from toolchain.buildsense.ingestion.run_processors.options_extrator import get_pants_options
from toolchain.buildsense.records.run_info import RunInfo, ServerInfo
from toolchain.buildsense.test_utils.data_loader import insert_build_data
from toolchain.buildsense.test_utils.fixtures_loader import load_bytes_fixture, load_fixture
from toolchain.django.site.models import Customer, Repo, ToolchainUser
from toolchain.util.test.elastic_search_util import DummyElasticRequests


def _insert_to_dynamo(
    pdi: PantsDataIngestion,
    user: ToolchainUser,
    build_time: datetime.datetime,
    fixture_id: int,
    server_info: ServerInfo,
) -> RunInfo:
    build_data = load_fixture(f"sample{fixture_id}")
    run_info = build_data["run_info"]
    run_info["branch"] = str(fixture_id)
    run_info["timestamp"] = int(build_time.replace(tzinfo=datetime.timezone.utc).timestamp())
    created, run_info = insert_build_data(pdi, build_data, user, server_info)
    assert created is True
    return run_info


def _prepare_build(repo: Repo, user: ToolchainUser) -> tuple[str, dict, RunInfo]:
    RunInfoTable.create_table()
    pdi = PantsDataIngestion.for_repo(repo)
    build_time = datetime.datetime(2019, 10, 28, 2, 17, 31, tzinfo=datetime.timezone.utc)
    raw_data = load_fixture("sample8")
    run_id = "pants_run_2019_09_18_13_23_26_11_454abc7b5ac5497486a1b42c9affc9d4"
    s3 = boto3.client("s3")
    key = f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.pk}/{user.api_id}/{run_id}/final.json"
    s3.put_object(Bucket="fake-test-buildsense-bucket", Key=key, Body=json.dumps(raw_data).encode())
    server_info = ServerInfo(
        request_id=str(uuid.uuid4()),
        accept_time=build_time,
        stats_version="1",
        environment="bisque-soup",
        s3_bucket="fake-test-buildsense-bucket",
        s3_key=key,
    )
    run_info = _insert_to_dynamo(pdi, user, build_time, 8, server_info)
    return run_id, raw_data, run_info


def prepare_build_with_artifacts(
    repo: Repo, user: ToolchainUser, artifact_name: str, runtime: int | None = None
) -> RunInfo:
    run_id, expected_raw_data, run_info = _prepare_build(repo, user)
    add_build_artifacts(repo, user, run_id, add_log=False, artifacts={artifact_name: "FAILURE"}, runtime=runtime)
    return run_info


def add_build_artifacts(
    repo: Repo,
    user: ToolchainUser,
    run_id: str,
    add_log: bool,
    artifacts: dict[str, str | None],
    add_options: bool = False,
    build_stats: dict | None = None,
    runtime: int | None = None,
) -> None:
    store = RunInfoRawStore.for_repo(repo)
    assert artifacts
    artifacts_work_units = []
    for artifact_name, result in artifacts.items():
        afu = {
            "work_unit_id": "4ff3cc029d949f9c",
            "description": "Run Pytest",
            "name": "pants.backend.python.goals.pytest_runner.run_python_test",
            "artifacts": artifact_name,
            "content_types": ["text/plain"],
        }
        if result:
            afu["result"] = result
        if runtime is not None:
            afu["run_time_msec"] = runtime  # type: ignore[assignment]
        artifacts_work_units.append(afu)
        store.save_build_json_file(
            run_id=run_id,
            json_bytes_or_file=json.dumps(
                [
                    {
                        "name": "stdout",
                        "content_type": "text/plain",
                        "content": load_bytes_fixture("pytest_success_stdout.txt").decode(),
                    }
                ]
            ).encode(),
            name=artifact_name,
            user_api_id=user.api_id,
            mode=WriteMode.OVERWRITE,
            dry_run=False,
            is_compressed=False,
        )
    build_artifact_groups = {"test": artifacts_work_units}
    if add_log:
        build_artifact_groups["logs"] = [
            {"name": "Logs", "description": "Pants run log", "artifacts": "pants_run_log.txt"}
        ]
    if add_options:
        _, artifact_desc = get_pants_options(build_stats)  # type: ignore[misc,arg-type]
        build_artifact_groups[artifact_desc["name"]] = [artifact_desc]  # type: ignore[list-item,index]

    store.save_build_json_file(
        run_id=run_id,
        json_bytes_or_file=json.dumps(build_artifact_groups).encode(),
        name="artifacts_work_units",
        user_api_id=user.api_id,
        mode=WriteMode.OVERWRITE,
        dry_run=False,
        is_compressed=False,
    )


@pytest.mark.django_db()
class BaseQueriesTests:
    @pytest.fixture(autouse=True)
    def _es_mock(self):
        DummyElasticRequests.reset()

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_dynamodb(), mock_s3():
            create_s3_bucket("fake-test-buildsense-bucket")
            yield

    @pytest.fixture()
    def user(self) -> ToolchainUser:
        user = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        Customer.create(slug="jerry", name="Jerry Seinfeld Inc").add_user(user)
        return user

    @pytest.fixture()
    def repo(self, user: ToolchainUser) -> Repo:
        customer = user.customers.first()
        return Repo.create("funnyguy", customer=customer, name="Jerry Seinfeld is a funny guy")


class TestBuildDataQueries(BaseQueriesTests):
    def _seed_dynamodb_data(self, repo: Repo, user: ToolchainUser, base_time: datetime.datetime) -> list[RunInfo]:
        RunInfoTable.create_table()
        dummy_server_info = ServerInfo(
            request_id=str(uuid.uuid4()),
            accept_time=base_time,
            stats_version="1",
            environment="bisque-soup",
            s3_bucket="fake-bucket",
            s3_key="fake-key",
        )
        base_time = base_time or utcnow()
        build_time = base_time
        pdi = PantsDataIngestion.for_repo(repo)
        run_infos = []
        for fixture_id in range(1, 7):
            run_info = _insert_to_dynamo(pdi, user, build_time, fixture_id, dummy_server_info)
            build_time = build_time + datetime.timedelta(minutes=12)
            run_infos.append(run_info)
        return run_infos

    def test_search_all_matching(self, repo: Repo, user: ToolchainUser) -> None:
        customer_id = repo.customer_id
        queries = BuildsQueries.for_customer_id(customer_id)
        base_time = utcnow() - datetime.timedelta(days=18)
        run_infos = self._seed_dynamodb_data(repo, user, base_time)
        DummyElasticRequests.add_search_response(run_infos[2:4])
        field_map = {"cmd_line": "test", "outcome": "FAILURE"}
        search_result = queries.search_all_matching(
            field_map=field_map, repo_id=repo.pk, sort="timestamp", page_size=15
        )
        run_infos = search_result.results
        assert len(run_infos) == 2
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "sort": ["timestamp", {"server_info.accept_time": {"order": "desc"}}, "_id"],
            "size": 15,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": customer_id}},
                        {"term": {"repo_id": repo.pk}},
                        {"match": {"cmd_line": "test"}},
                        {"term": {"outcome": "FAILURE"}},
                    ]
                }
            },
        }

    def test_search_all_matching_empty_results(self, repo: Repo, user: ToolchainUser) -> None:
        customer_id = repo.customer_id
        queries = BuildsQueries.for_customer_id(customer_id)
        DummyElasticRequests.add_empty_search_response()
        field_map = {"cmd_line": "test", "outcome": "FAILURE"}
        search_result = queries.search_all_matching(field_map=field_map, repo_id=repo.pk, page_size=12)
        run_infos = search_result.results
        assert not run_infos
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "sort": [{"timestamp": {"order": "desc"}}, {"server_info.accept_time": {"order": "desc"}}, "_id"],
            "size": 12,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": customer_id}},
                        {"term": {"repo_id": repo.pk}},
                        {"match": {"cmd_line": "test"}},
                        {"term": {"outcome": "FAILURE"}},
                    ]
                }
            },
        }


class TestGetBuild(BaseQueriesTests):
    def test_get_build(self, repo: Repo, user: ToolchainUser) -> None:
        run_id, _, expected_run_info = _prepare_build(repo, user)
        queries = BuildsQueries.for_customer_id(repo.customer_id)
        run_info = queries.get_build(repo_id=repo.pk, user_api_id=user.api_id, run_id=run_id)
        assert expected_run_info == run_info

    def test_get_build_raw_data(self, repo: Repo, user: ToolchainUser) -> None:
        run_id, expected_raw_data, _ = _prepare_build(repo, user)
        queries = BuildsQueries.for_customer_id(repo.customer_id)
        raw_data = queries.get_build_raw_data(repo=repo, user_api_id=user.api_id, run_id=run_id)
        assert expected_raw_data == raw_data

    def test_get_build_without_user_api_id(self, repo: Repo, user: ToolchainUser) -> None:
        customer_id = repo.customer_id
        run_id, _, run_info = _prepare_build(repo, user)
        DummyElasticRequests.add_search_response([run_info])
        queries = BuildsQueries.for_customer_id(customer_id)
        assert queries.get_build(repo_id=repo.pk, user_api_id=None, run_id=run_id) == run_info
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": customer_id}},
                        {"term": {"repo_id": repo.pk}},
                        {"term": {"run_id": run_id}},
                    ]
                }
            }
        }

    def test_get_build_without_user_api_id_no_build(self, repo: Repo, user: ToolchainUser) -> None:
        customer_id = repo.customer_id
        DummyElasticRequests.add_empty_search_response()
        queries = BuildsQueries.for_customer_id(customer_id)
        build_data = queries.get_build(repo_id=repo.pk, user_api_id=None, run_id="coffee-table-book")
        assert build_data is None
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": customer_id}},
                        {"term": {"repo_id": repo.pk}},
                        {"term": {"run_id": "coffee-table-book"}},
                    ]
                }
            }
        }

    def test_get_build_artifact_doesnt_exist(self, repo: Repo, user: ToolchainUser) -> None:
        run_id = prepare_build_with_artifacts(repo, user, "festivus_stdout.txt").run_id
        queries = BuildsQueries.for_customer_id(repo.customer_id)
        artifact_file = queries.get_build_artifact(repo, user.api_id, run_id, "tinsel_stdout.txt")
        assert artifact_file is None

    def test_get_build_artifacts(self, repo: Repo, user: ToolchainUser) -> None:
        run_info = prepare_build_with_artifacts(repo, user, "festivus_stdout.txt")
        queries = BuildsQueries.for_customer_id(repo.customer_id)
        artifacts = queries.get_build_artifacts(repo, run_info)
        assert artifacts == {
            "test": {
                "type": "goal",
                "artifacts": [
                    {
                        "name": "festivus_stdout.txt",
                        "description": "Run Pytest",
                        "group": "pants.backend.python.goals.pytest_runner.run_python_test",
                        "result": "FAILURE",
                        "content_types": ["text/plain"],
                    }
                ],
            }
        }

    def test_get_build_artifacts_with_runtime(self, repo: Repo, user: ToolchainUser) -> None:
        run_info = prepare_build_with_artifacts(repo, user, "festivus_stdout.txt", runtime=87879)
        queries = BuildsQueries.for_customer_id(repo.customer_id)
        artifacts = queries.get_build_artifacts(repo, run_info)
        assert artifacts == {
            "test": {
                "type": "goal",
                "artifacts": [
                    {
                        "name": "festivus_stdout.txt",
                        "description": "Run Pytest",
                        "run_time_msec": 87879,
                        "group": "pants.backend.python.goals.pytest_runner.run_python_test",
                        "result": "FAILURE",
                        "content_types": ["text/plain"],
                    }
                ],
            }
        }
