# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import zlib
from io import BytesIO

import pytest
from moto import mock_s3

from toolchain.aws.test_utils.s3_utils import create_s3_bucket
from toolchain.base.datetime_tools import utcnow
from toolchain.buildsense.ingestion.run_info_raw_store import RunInfoRawStore
from toolchain.buildsense.ingestion.run_processors.artifacts_test import assert_pants_options
from toolchain.buildsense.ingestion.run_processors.processor import ProcessPantsData
from toolchain.buildsense.records.run_info import RunInfo, ScmProvider, ServerInfo
from toolchain.buildsense.test_utils.data_loader import parse_run_info
from toolchain.buildsense.test_utils.fixtures_loader import load_bytes_fixture, load_fixture
from toolchain.django.site.models import Customer, Repo, ToolchainUser
from toolchain.github_integration.client.repo_clients_test import (
    add_github_pr_response_for_repo,
    add_github_push_response_for_repo,
)


@pytest.mark.django_db()
class TestProcessPantsRuns:
    _BUCKET = "fake-test-buildsense-bucket"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3():
            create_s3_bucket(self._BUCKET)
            yield

    def _load_fixture(
        self, fixture_name: str, repo: Repo, user: ToolchainUser, stats_version: str = "1"
    ) -> tuple[RunInfo, dict]:
        build_data = load_fixture(fixture_name)
        run_id = build_data["run_info"]["id"]
        server_info = ServerInfo(
            request_id=fixture_name,
            accept_time=utcnow(),
            stats_version=stats_version,
            environment="gold",
            s3_bucket=self._BUCKET,
            s3_key=f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.id}/{user.api_id}/{run_id}/final.json",
        )
        run_info = parse_run_info(fixture_data=build_data, repo=repo, user=user, server_info=server_info)
        run_info.title = None
        return run_info, build_data

    @pytest.fixture()
    def customer(self) -> Customer:
        return Customer.create(slug="jerry", name="Jerry Seinfeld Inc")

    @pytest.fixture()
    def user(self, customer: Customer) -> ToolchainUser:
        user = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        customer.add_user(user)
        return user

    @pytest.fixture()
    def repo(self, customer: Customer) -> Repo:
        return Repo.create("funnyguy", customer=customer, name="Jerry Seinfeld is a funny guy")

    @pytest.mark.parametrize(
        ("fixture", "expected_run_time"),
        [
            ("sample1", datetime.timedelta(seconds=17.095)),
            ("sample2", datetime.timedelta(seconds=11.518)),
            ("sample3", datetime.timedelta(seconds=2.814)),
            ("sample4", datetime.timedelta(seconds=3.291)),
            ("sample5", datetime.timedelta(seconds=4.729)),
            ("sample6", datetime.timedelta(seconds=8.921)),
        ],
    )
    def test_set_run_time(
        self, user: ToolchainUser, repo: Repo, fixture: str, expected_run_time: datetime.timedelta
    ) -> None:
        run_info, build_data = self._load_fixture(fixture, repo, user)
        assert run_info.run_time is None
        result = ProcessPantsData(run_info, ScmProvider.GITHUB).pipeline(build_data, None)
        assert result.run_info.run_time == expected_run_time
        assert result.files == tuple()
        assert result.has_metrics is False

    def test_create_zipkin_trace_files(self, user: ToolchainUser, repo: Repo) -> None:
        run_info, build_data = self._load_fixture("build_end_workunits_v3", repo, user, stats_version="3")
        assert run_info.run_time is None
        result = ProcessPantsData(run_info, ScmProvider.GITHUB).pipeline(build_data, None)
        assert result.run_info.run_time == datetime.timedelta(seconds=28, microseconds=624000)
        assert result.has_metrics is False
        assert len(result.files) == 3
        assert result.files[0].name == "zipkin_trace.json"
        assert result.files[0].content_type == "application/json"
        assert result.files[0].compressed is True
        zipkin_trace = zlib.decompress(result.files[0].content)
        assert len(zipkin_trace) == 65_717
        assert json.loads(zipkin_trace) == load_fixture("zipkin_trace_1")

    def test_create_zipkin_trace_files_empty_workunit(self, user: ToolchainUser, repo: Repo) -> None:
        run_info, build_data = self._load_fixture("build_end_workunits_v3", repo, user, stats_version="3")
        build_data["workunits"].clear()
        assert run_info.run_time is None
        result = ProcessPantsData(run_info, ScmProvider.GITHUB).pipeline(build_data, None)
        assert result.has_metrics is False
        assert result.run_info.run_time == datetime.timedelta(seconds=28, microseconds=624000)
        assert_pants_options(result.files)

    def test_update_ci_info_pr(self, httpx_mock, user: ToolchainUser, repo: Repo) -> None:
        run_info, build_data = self._load_fixture("ci_build_pr_final_1", repo, user, stats_version="2")
        assert run_info.branch == "pull/6490"
        assert run_info.ci_info is not None
        assert run_info.ci_info.link is None
        add_github_pr_response_for_repo(httpx_mock, repo, 6490, "pull_request_review_requested")
        assert run_info.run_time is None
        result = ProcessPantsData(run_info, ScmProvider.GITHUB).pipeline(build_data, None)
        assert result.has_metrics is False
        assert run_info.branch == "helen"
        assert run_info.ci_info.link == "https://github.com/toolchainlabs/toolchain/pull/5769"
        assert run_info.title == "Parse webhooks responses."
        assert result.run_info.run_time == datetime.timedelta(seconds=10, microseconds=657000)
        assert result.files == tuple()
        assert httpx_mock.get_request() is not None

    def test_update_ci_info_missing_pr_info(self, httpx_mock, user: ToolchainUser, repo: Repo) -> None:
        run_info, build_data = self._load_fixture("ci_build_pr_final_1", repo, user, stats_version="2")
        assert run_info.branch == "pull/6490"
        add_github_pr_response_for_repo(httpx_mock, repo, 6490)
        assert run_info.run_time is None
        result = ProcessPantsData(run_info, ScmProvider.GITHUB).pipeline(build_data, None)
        assert result.has_metrics is False
        assert run_info.branch == "pull/6490"
        assert run_info.ci_info is not None
        assert run_info.ci_info.link is None
        assert run_info.title is None
        assert result.run_info.run_time == datetime.timedelta(seconds=10, microseconds=657000)
        assert result.files == tuple()
        assert httpx_mock.get_request() is not None

    def test_update_ci_info_branch(self, httpx_mock, user: ToolchainUser, repo: Repo) -> None:
        add_github_push_response_for_repo(
            httpx_mock,
            repo,
            branch="master",
            commit_sha="3962394f3b3413389c911d3cfb9dbf45fe735a1f",
            fixture="repo_push",
        )
        run_info, build_data = self._load_fixture("ci_build_branch_final_1", repo, user, stats_version="2")
        assert run_info.branch == "master"
        assert run_info.run_time is None
        result = ProcessPantsData(run_info, ScmProvider.GITHUB).pipeline(build_data, None)
        assert result.has_metrics is False
        assert run_info.branch == "master"
        assert run_info.ci_info is not None
        assert (
            run_info.ci_info.link
            == "https://github.com/toolchainlabs/toolchain/commit/bb7dc6a6e4fdc8271d455dc423f0f5241fee5804"
        )
        assert run_info.title == "Update ./pants runner script. (#6600)"
        assert httpx_mock.get_request() is not None
        assert result.run_info.run_time == datetime.timedelta(seconds=443, microseconds=44000)
        assert result.files == tuple()

    def test_update_ci_info_branch_missing_commit_info(self, httpx_mock, user: ToolchainUser, repo: Repo) -> None:
        add_github_push_response_for_repo(
            httpx_mock, repo, branch="master", commit_sha="3962394f3b3413389c911d3cfb9dbf45fe735a1f"
        )
        run_info, build_data = self._load_fixture("ci_build_branch_final_1", repo, user, stats_version="2")
        assert run_info.branch == "master"
        assert run_info.run_time is None
        result = ProcessPantsData(run_info, ScmProvider.GITHUB).pipeline(build_data, None)
        assert result.has_metrics is False
        assert run_info.branch == "master"
        assert run_info.ci_info is not None
        assert run_info.ci_info.link is None
        assert run_info.title is None
        assert httpx_mock.get_request() is not None
        assert result.run_info.run_time == datetime.timedelta(seconds=443, microseconds=44000)
        assert result.files == tuple()

    def test_extract_artifacts_with_standalone(self, user: ToolchainUser, repo: Repo) -> None:
        run_info, build_data = self._load_fixture("run_with_pytest_xml_results", repo, user, stats_version="3")
        store = RunInfoRawStore.for_run_info(run_info)
        coverage_xml = BytesIO(load_bytes_fixture("pytest_coverage.xml"))
        store.save_artifact(
            run_id=run_info.run_id,
            user_api_id=user.api_id,
            content_type="application/xml",
            name="coverage_xml_coverage.xml",
            metadata={"workunit_id": "6c093303c17dff43"},
            fp=coverage_xml,
            is_compressed=False,
        )
        result = ProcessPantsData(run_info, ScmProvider.GITHUB).pipeline(build_data, None)
        assert result.has_metrics is False
        assert len(result.files) == 6
        assert [fl.name for fl in result.files] == [
            "zipkin_trace.json",
            "pytest_results.json",
            "test_4b44bcd6813e75cb_artifacts.json",
            "coverage_summary.json",
            "pants_options.json",
            "artifacts_work_units.json",
        ]
        assert json.loads(result.files[-1].content) == {
            "pants_options": [
                {
                    "artifacts": "pants_options.json",
                    "description": "Pants Options",
                    "name": "pants_options",
                    "content_types": ["pants_options"],
                },
            ],
            "test": [
                {
                    "work_unit_id": "6077393d5f2e7d81",
                    "name": "pytest_results",
                    "description": "Test results",
                    "artifacts": "pytest_results.json",
                    "result": "SUCCESS",
                    "content_types": ["pytest_results/v2"],
                },
                {
                    "work_unit_id": "330b79f44dc69fdb",
                    "name": "pants.backend.python.goals.pytest_runner.run_python_test",
                    "description": "Run Pytest",
                    "artifacts": "test_4b44bcd6813e75cb_artifacts.json",
                    "content_types": ["text/plain"],
                },
                {
                    "work_unit_id": "6c093303c17dff43",
                    "name": "coverage_summary",
                    "description": "Code Coverage Summary",
                    "artifacts": "coverage_summary.json",
                    "content_types": ["coverage_summary"],
                },
            ],
        }
        assert json.loads(result.files[1].content) == [
            {
                "name": "Test Results",
                "content_type": "pytest_results/v2",
                "content": {
                    "test_runs": [
                        {
                            "tests": [
                                {
                                    "name": "src.python.toolchain.aws.s3_test.test_s3_url_functionality",
                                    "test_file_path": "src/python/toolchain/aws/s3_test.py",
                                    "time": 1.35,
                                    "tests": [
                                        {
                                            "name": "dummy/path-s3://testbucket/dummy/path-http://testbucket.s3.amazonaws.com/dummy/path",
                                            "time": 1.194,
                                            "outcome": "pass",
                                        },
                                        {
                                            "name": "dummy/path/-s3://testbucket/dummy/path/-http://testbucket.s3.amazonaws.com/dummy/path/",
                                            "time": 0.077,
                                            "outcome": "pass",
                                        },
                                        {
                                            "name": "/dummy/path-s3://testbucket//dummy/path-http://testbucket.s3.amazonaws.com//dummy/path",
                                            "time": 0.08,
                                            "outcome": "pass",
                                        },
                                    ],
                                },
                                {
                                    "name": "src.python.toolchain.aws.s3_test.test_parse_s3_url_failure",
                                    "test_file_path": "src/python/toolchain/aws/s3_test.py",
                                    "time": 0.16,
                                    "tests": [
                                        {"name": "http://foo.com/bar/baz", "time": 0.079, "outcome": "pass"},
                                        {"name": "s4://blah/blah/blah/", "time": 0.082, "outcome": "pass"},
                                    ],
                                },
                                {
                                    "name": "src.python.toolchain.aws.s3_test",
                                    "test_file_path": "src/python/toolchain/aws/s3_test.py",
                                    "time": 1.28,
                                    "tests": [
                                        {"name": "test_exists_and_delete", "time": 0.157, "outcome": "pass"},
                                        {"name": "test_keys_with_prefix", "time": 0.108, "outcome": "pass"},
                                        {"name": "test_upload_json_str", "time": 0.192, "outcome": "pass"},
                                        {"name": "test_reading_and_writing_content", "time": 0.078, "outcome": "pass"},
                                        {"name": "test_get_content_or_none", "time": 0.092, "outcome": "pass"},
                                        {"name": "test_upload_file", "time": 0.091, "outcome": "pass"},
                                        {"name": "test_download_file", "time": 0.111, "outcome": "pass"},
                                        {"name": "test_copy_object", "time": 0.123, "outcome": "pass"},
                                        {"name": "test_upload_directory", "time": 0.085, "outcome": "pass"},
                                        {"name": "test_download_directory", "time": 0.24, "outcome": "pass"},
                                    ],
                                },
                            ],
                            "timing": {"total": 2.79},
                            "target": "src/python/toolchain/aws/s3_test.py",
                            "outputs": {"stdout": None, "stderr": None},
                        }
                    ]
                },
            }
        ]
        assert json.loads(result.files[3].content) == [
            {
                "name": "Code Coverage Summary",
                "content_type": "coverage_summary",
                "content": {"lines_covered": 747, "lines_uncovered": 155},
            }
        ]

    def test_extract_artifacts_pytest_with_addresses(self, user: ToolchainUser, repo: Repo) -> None:
        run_info, build_data = self._load_fixture("pants_pytest_with_address", repo, user, stats_version="3")
        result = ProcessPantsData(run_info, ScmProvider.GITHUB).pipeline(build_data, None)
        assert result.has_metrics is True
        assert len(result.files) == 6
        assert [fl.name for fl in result.files] == [
            "zipkin_trace.json",
            "pytest_results.json",
            "aggregate_metrics.json",
            "pants_options.json",
            "targets_specs.json",
            "artifacts_work_units.json",
        ]

        assert json.loads(result.files[-1].content) == {
            "test": [
                {
                    "work_unit_id": "58c39e1f3d0ee306",
                    "name": "pytest_results",
                    "description": "Test results",
                    "artifacts": "pytest_results.json",
                    "content_types": ["pytest_results/v2"],
                    "result": "SUCCESS",
                },
            ],
            "metrics": [
                {
                    "name": "metrics",
                    "description": "Run metrics",
                    "artifacts": "aggregate_metrics.json",
                    "content_types": ["work_unit_metrics"],
                }
            ],
            "pants_options": [
                {
                    "name": "pants_options",
                    "description": "Pants Options",
                    "artifacts": "pants_options.json",
                    "content_types": ["pants_options"],
                }
            ],
            "targets_specs": [
                {
                    "name": "targets_specs",
                    "description": "Expanded targets specs",
                    "artifacts": "targets_specs.json",
                    "content_types": ["targets_specs"],
                }
            ],
        }
        assert json.loads(result.files[1].content) == [
            {
                "name": "Test Results",
                "content_type": "pytest_results/v2",
                "content": {
                    "test_runs": [
                        {
                            "tests": [
                                {
                                    "name": "src.python.toolchain.github_integration.app_client_test.TestGithubRepoClient",
                                    "test_file_path": "src/python/toolchain/github_integration/app_client_test.py:tests",
                                    "time": 4.35,
                                    "tests": [
                                        {"name": "test_get_client", "time": 1.97, "outcome": "pass"},
                                        {"name": "test_github_api_responses", "time": 1.111, "outcome": "pass"},
                                        {"name": "test_list_webhooks", "time": 0.158, "outcome": "pass"},
                                        {"name": "test_list_webhooks_http_error", "time": 0.097, "outcome": "pass"},
                                        {"name": "test_create_webhook", "time": 0.145, "outcome": "pass"},
                                        {
                                            "name": "test_create_webhook_invalid_secret",
                                            "time": 0.117,
                                            "outcome": "pass",
                                        },
                                        {"name": "test_delete_webhook", "time": 0.12, "outcome": "pass"},
                                        {
                                            "name": "test_delete_webhook_invalid_webhook_id",
                                            "time": 0.113,
                                            "outcome": "pass",
                                        },
                                        {"name": "test_update_webhook", "time": 0.098, "outcome": "pass"},
                                        {"name": "test_get_workflow_actions_run", "time": 0.332, "outcome": "pass"},
                                        {
                                            "name": "test_get_workflow_actions_run_not_found",
                                            "time": 0.093,
                                            "outcome": "pass",
                                        },
                                    ],
                                },
                                {
                                    "name": "src.python.toolchain.github_integration.app_client_test.TestGithubAppClient",
                                    "test_file_path": "src/python/toolchain/github_integration/app_client_test.py:tests",
                                    "time": 0.71,
                                    "tests": [
                                        {
                                            "name": "test_get_installation_access_token",
                                            "time": 0.119,
                                            "outcome": "pass",
                                        },
                                        {"name": "test_list_installations", "time": 0.592, "outcome": "pass"},
                                    ],
                                },
                            ],
                            "timing": {"total": 5.06},
                            "target": "src/python/toolchain/github_integration/app_client_test.py:tests",
                            "outputs": {
                                "stdout": "\x1b[1m============================= test session starts ==============================\x1b[0m\nplatform darwin -- Python 3.8.12, pytest-6.2.5, py-1.10.0, pluggy-1.0.0\nrootdir: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionJoDkjt\nplugins: responses-0.5.0, anyio-3.3.3, icdiff-0.5, django-4.4.0, cov-3.0.0, httpx-0.13.0\ncollected 13 items\n\nsrc/python/toolchain/github_integration/app_client_test.py \x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m [100%]\x1b[0m\n\n- generated xml file: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionJoDkjt/src.python.toolchain.github_integration.app_client_test.py.tests.xml -\n\n\n\x1b[32m============================== \x1b[32m\x1b[1m13 passed\x1b[0m\x1b[32m in 9.09s\x1b[0m\x1b[32m ==============================\x1b[0m\n",
                                "stderr": "/Users/asher/.cache/pants/named_caches/pex_root/venvs/short/cb65cd13/lib/python3.8/site-packages/django/apps/registry.py:91: RemovedInDjango41Warning: 'django_prometheus' defines default_app_config = 'django_prometheus.apps.DjangoPrometheusConfig'. Django now detects this configuration automatically. You can remove default_app_config.\n  app_config = AppConfig.create(entry)\n",
                            },
                        },
                        {
                            "tests": [
                                {
                                    "name": "src.python.toolchain.github_integration.config_test.TestGithubIntegrationConfig",
                                    "test_file_path": "src/python/toolchain/github_integration/config_test.py:tests",
                                    "time": 0.04,
                                    "tests": [
                                        {"name": "test_missing_secret", "time": 0.031, "outcome": "pass"},
                                        {"name": "test_config", "time": 0.012, "outcome": "pass"},
                                    ],
                                }
                            ],
                            "timing": {"total": 0.04},
                            "target": "src/python/toolchain/github_integration/config_test.py:tests",
                            "outputs": {
                                "stdout": "\x1b[1m============================= test session starts ==============================\x1b[0m\nplatform darwin -- Python 3.8.12, pytest-6.2.5, py-1.10.0, pluggy-1.0.0\nrootdir: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionZ441eX\nplugins: responses-0.5.0, anyio-3.3.3, icdiff-0.5, django-4.4.0, cov-3.0.0, httpx-0.13.0\ncollected 2 items\n\nsrc/python/toolchain/github_integration/config_test.py \x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m                [100%]\x1b[0m\n\n- generated xml file: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionZ441eX/src.python.toolchain.github_integration.config_test.py.tests.xml -\n\n\n\x1b[32m============================== \x1b[32m\x1b[1m2 passed\x1b[0m\x1b[32m in 7.47s\x1b[0m\x1b[32m ===============================\x1b[0m\n",
                                "stderr": "/Users/asher/.cache/pants/named_caches/pex_root/venvs/short/cb65cd13/lib/python3.8/site-packages/django/apps/registry.py:91: RemovedInDjango41Warning: 'django_prometheus' defines default_app_config = 'django_prometheus.apps.DjangoPrometheusConfig'. Django now detects this configuration automatically. You can remove default_app_config.\n  app_config = AppConfig.create(entry)\n",
                            },
                        },
                        {
                            "tests": [
                                {
                                    "name": "src.python.toolchain.github_integration.models_test.TestGithubRepo",
                                    "test_file_path": "src/python/toolchain/github_integration/models_test.py:tests",
                                    "time": 2.85,
                                    "tests": [
                                        {"name": "test_activate_create", "time": 1.669, "outcome": "pass"},
                                        {"name": "test_activate_different_customer", "time": 0.08, "outcome": "pass"},
                                        {"name": "test_activate_already_active", "time": 0.648, "outcome": "pass"},
                                        {"name": "test_deactivate_active", "time": 0.099, "outcome": "pass"},
                                        {"name": "test_deactivate_inactive", "time": 0.124, "outcome": "pass"},
                                        {"name": "test_get_by_github_repo_id", "time": 0.057, "outcome": "pass"},
                                        {"name": "test_get_webhook_secret", "time": 0.066, "outcome": "pass"},
                                        {"name": "test_get_by_id", "time": 0.058, "outcome": "pass"},
                                        {"name": "test_activate_create_long_name", "time": 0.046, "outcome": "pass"},
                                    ],
                                },
                                {
                                    "name": "src.python.toolchain.github_integration.models_test.TestGithubRepoStatsConifguration",
                                    "test_file_path": "src/python/toolchain/github_integration/models_test.py:tests",
                                    "time": 2.09,
                                    "tests": [
                                        {
                                            "name": "test_github_repo_stats_configuration",
                                            "time": 2.087,
                                            "outcome": "pass",
                                        }
                                    ],
                                },
                            ],
                            "timing": {"total": 4.94},
                            "target": "src/python/toolchain/github_integration/models_test.py:tests",
                            "outputs": {
                                "stdout": "\x1b[1m============================= test session starts ==============================\x1b[0m\nplatform darwin -- Python 3.8.12, pytest-6.2.5, py-1.10.0, pluggy-1.0.0\nrootdir: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionEQONQW\nplugins: responses-0.5.0, anyio-3.3.3, icdiff-0.5, django-4.4.0, cov-3.0.0, httpx-0.13.0\ncollected 10 items\n\nsrc/python/toolchain/github_integration/models_test.py \x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m        [100%]\x1b[0m\n\n- generated xml file: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionEQONQW/src.python.toolchain.github_integration.models_test.py.tests.xml -\n\n\n\x1b[32m============================== \x1b[32m\x1b[1m10 passed\x1b[0m\x1b[32m in 7.86s\x1b[0m\x1b[32m ==============================\x1b[0m\n",
                                "stderr": "/Users/asher/.cache/pants/named_caches/pex_root/venvs/short/78ed784e/lib/python3.8/site-packages/django/apps/registry.py:91: RemovedInDjango41Warning: 'django_prometheus' defines default_app_config = 'django_prometheus.apps.DjangoPrometheusConfig'. Django now detects this configuration automatically. You can remove default_app_config.\n  app_config = AppConfig.create(entry)\n",
                            },
                        },
                        {
                            "tests": [
                                {
                                    "name": "src.python.toolchain.github_integration.repo_data_store_test.TestGithubRepoDataStore",
                                    "test_file_path": "src/python/toolchain/github_integration/repo_data_store_test.py:tests",
                                    "time": 10.62,
                                    "tests": [
                                        {"name": "test_store_pr", "time": 6.47, "outcome": "pass"},
                                        {"name": "test_get_pr", "time": 0.671, "outcome": "pass"},
                                        {"name": "test_get_non_existent_pr", "time": 0.425, "outcome": "pass"},
                                        {
                                            "name": "test_for_github_repo_id_invalid_repo",
                                            "time": 0.373,
                                            "outcome": "pass",
                                        },
                                        {"name": "test_store_push", "time": 0.406, "outcome": "pass"},
                                        {"name": "test_store_push_nested_branch", "time": 0.388, "outcome": "pass"},
                                        {"name": "test_get_push", "time": 0.298, "outcome": "pass"},
                                        {"name": "test_save_repo_stats_data", "time": 0.403, "outcome": "pass"},
                                        {"name": "test_save_check_run", "time": 0.502, "outcome": "pass"},
                                        {"name": "test_get_check_run", "time": 0.335, "outcome": "pass"},
                                        {"name": "test_get_check_run_missing", "time": 0.349, "outcome": "pass"},
                                    ],
                                },
                                {
                                    "name": "src.python.toolchain.github_integration.repo_data_store_test.TestTravisRepoDataStore",
                                    "test_file_path": "src/python/toolchain/github_integration/repo_data_store_test.py:tests",
                                    "time": 1.06,
                                    "tests": [
                                        {"name": "test_save_build", "time": 0.299, "outcome": "pass"},
                                        {"name": "test_get_build_not_existing", "time": 0.285, "outcome": "pass"},
                                        {"name": "test_get_build", "time": 0.475, "outcome": "pass"},
                                    ],
                                },
                            ],
                            "timing": {"total": 11.68},
                            "target": "src/python/toolchain/github_integration/repo_data_store_test.py:tests",
                            "outputs": {
                                "stdout": "\x1b[1m============================= test session starts ==============================\x1b[0m\nplatform darwin -- Python 3.8.12, pytest-6.2.5, py-1.10.0, pluggy-1.0.0\nrootdir: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionRpYp0M\nplugins: responses-0.5.0, anyio-3.3.3, icdiff-0.5, django-4.4.0, cov-3.0.0, httpx-0.13.0\ncollected 14 items\n\nsrc/python/toolchain/github_integration/repo_data_store_test.py \x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m [ 57%]\n\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m                                                                   [100%]\x1b[0m\n\n- generated xml file: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionRpYp0M/src.python.toolchain.github_integration.repo_data_store_test.py.tests.xml -\n\n\n\x1b[32m============================= \x1b[32m\x1b[1m14 passed\x1b[0m\x1b[32m in 14.89s\x1b[0m\x1b[32m ==============================\x1b[0m\n",
                                "stderr": "/Users/asher/.cache/pants/named_caches/pex_root/venvs/short/c0babb84/lib/python3.8/site-packages/django/apps/registry.py:91: RemovedInDjango41Warning: 'django_prometheus' defines default_app_config = 'django_prometheus.apps.DjangoPrometheusConfig'. Django now detects this configuration automatically. You can remove default_app_config.\n  app_config = AppConfig.create(entry)\n",
                            },
                        },
                        {
                            "tests": [
                                {
                                    "name": "src.python.toolchain.github_integration.api.resources_check_test.TestResourcesCheckz",
                                    "test_file_path": "src/python/toolchain/github_integration/api/resources_check_test.py:tests",
                                    "time": 6.53,
                                    "tests": [
                                        {"name": "test_resources_check_view", "time": 6.116, "outcome": "pass"},
                                        {
                                            "name": "test_resources_check_view_empty_db",
                                            "time": 0.411,
                                            "outcome": "pass",
                                        },
                                    ],
                                }
                            ],
                            "timing": {"total": 6.53},
                            "target": "src/python/toolchain/github_integration/api/resources_check_test.py:tests",
                            "outputs": {
                                "stdout": "\x1b[1m============================= test session starts ==============================\x1b[0m\nplatform darwin -- Python 3.8.12, pytest-6.2.5, py-1.10.0, pluggy-1.0.0\nrootdir: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionOeXQLd\nplugins: responses-0.5.0, anyio-3.3.3, icdiff-0.5, django-4.4.0, cov-3.0.0, httpx-0.13.0\ncollected 2 items\n\nsrc/python/toolchain/github_integration/api/resources_check_test.py \x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m   [100%]\x1b[0m\n\n- generated xml file: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionOeXQLd/src.python.toolchain.github_integration.api.resources_check_test.py.tests.xml -\n\n\n\x1b[32m============================== \x1b[32m\x1b[1m2 passed\x1b[0m\x1b[32m in 8.06s\x1b[0m\x1b[32m ===============================\x1b[0m\n",
                                "stderr": "/Users/asher/.cache/pants/named_caches/pex_root/venvs/short/001e0fdd/lib/python3.8/site-packages/django/apps/registry.py:91: RemovedInDjango41Warning: 'django_prometheus' defines default_app_config = 'django_prometheus.apps.DjangoPrometheusConfig'. Django now detects this configuration automatically. You can remove default_app_config.\n  app_config = AppConfig.create(entry)\n",
                            },
                        },
                        {
                            "tests": [
                                {
                                    "name": "src.python.toolchain.github_integration.api.views_test.TestPullRequestView",
                                    "test_file_path": "src/python/toolchain/github_integration/api/views_test.py:tests",
                                    "time": 5.16,
                                    "tests": [
                                        {"name": "test_get_pr", "time": 4.917, "outcome": "pass"},
                                        {"name": "test_get_non_existent_pr", "time": 0.246, "outcome": "pass"},
                                    ],
                                },
                                {
                                    "name": "src.python.toolchain.github_integration.api.views_test.TestCommitView",
                                    "test_file_path": "src/python/toolchain/github_integration/api/views_test.py:tests",
                                    "time": 0.77,
                                    "tests": [
                                        {"name": "test_get_commit_nested_branch", "time": 0.229, "outcome": "pass"},
                                        {"name": "test_get_non_existent_commit", "time": 0.221, "outcome": "pass"},
                                        {"name": "test_get_commit_named_branch", "time": 0.321, "outcome": "pass"},
                                    ],
                                },
                                {
                                    "name": "src.python.toolchain.github_integration.api.views_test.TestPushView",
                                    "test_file_path": "src/python/toolchain/github_integration/api/views_test.py:tests",
                                    "time": 0.87,
                                    "tests": [
                                        {"name": "test_get_push_nested_branch", "time": 0.383, "outcome": "pass"},
                                        {"name": "test_get_non_existent_push", "time": 0.222, "outcome": "pass"},
                                        {"name": "test_get_push_named_branch", "time": 0.269, "outcome": "pass"},
                                    ],
                                },
                                {
                                    "name": "src.python.toolchain.github_integration.api.views_test.TestRepoWebhookView",
                                    "test_file_path": "src/python/toolchain/github_integration/api/views_test.py:tests",
                                    "time": 1.68,
                                    "tests": [
                                        {"name": "test_get_repo_secret", "time": 0.247, "outcome": "pass"},
                                        {
                                            "name": "test_get_repo_secret_inactive_repo",
                                            "time": 0.233,
                                            "outcome": "pass",
                                        },
                                        {"name": "test_get_repo_secret_no_secret", "time": 0.244, "outcome": "pass"},
                                        {"name": "test_get_repo_secret_no_repo", "time": 0.409, "outcome": "pass"},
                                        {"name": "test_post_webhook_missing_repo", "time": 0.293, "outcome": "pass"},
                                        {"name": "test_post_webhook_handled", "time": 0.256, "outcome": "pass"},
                                    ],
                                },
                                {
                                    "name": "src.python.toolchain.github_integration.api.views_test.TestAppWebhookView",
                                    "test_file_path": "src/python/toolchain/github_integration/api/views_test.py:tests",
                                    "time": 1.39,
                                    "tests": [
                                        {"name": "test_post_install_app_created", "time": 1.388, "outcome": "pass"}
                                    ],
                                },
                                {
                                    "name": "src.python.toolchain.github_integration.api.views_test.TestTravisWebhookView",
                                    "test_file_path": "src/python/toolchain/github_integration/api/views_test.py:tests",
                                    "time": 0.45,
                                    "tests": [
                                        {"name": "test_post_github_webhook", "time": 0.234, "outcome": "pass"},
                                        {"name": "test_post_github_webhook_no_repo", "time": 0.214, "outcome": "pass"},
                                    ],
                                },
                                {
                                    "name": "src.python.toolchain.github_integration.api.views_test.TestCIResolveViewTravis",
                                    "test_file_path": "src/python/toolchain/github_integration/api/views_test.py:tests",
                                    "time": 3.52,
                                    "tests": [
                                        {"name": "test_resolve_ci", "time": 0.475, "outcome": "pass"},
                                        {"name": "test_resolve_ci_key_too_long", "time": 0.433, "outcome": "pass"},
                                        {
                                            "name": "test_resolve_ci_fail_no_github_pr_info",
                                            "time": 0.328,
                                            "outcome": "pass",
                                        },
                                        {"name": "test_resolve_ci_fail_old_build", "time": 0.284, "outcome": "pass"},
                                        {"name": "test_resolve_ci_fail_invalid_job", "time": 0.279, "outcome": "pass"},
                                        {"name": "test_resolve_ci_fail_invalid_pr", "time": 0.285, "outcome": "pass"},
                                        {
                                            "name": "test_resolve_ci_fail_missing_env_vars",
                                            "time": 0.294,
                                            "outcome": "pass",
                                        },
                                        {
                                            "name": "test_resolve_ci_fail_missing_not_pull_request",
                                            "time": 0.41,
                                            "outcome": "pass",
                                        },
                                        {
                                            "name": "test_resolve_ci_fail_unknown_build_id",
                                            "time": 0.223,
                                            "outcome": "pass",
                                        },
                                        {"name": "test_resolve_ci_fail_not_travis", "time": 0.225, "outcome": "pass"},
                                        {"name": "test_resolve_ci_fail_build_state", "time": 0.284, "outcome": "pass"},
                                    ],
                                },
                                {
                                    "name": "src.python.toolchain.github_integration.api.views_test.TestCIResolveViewGithubActions",
                                    "test_file_path": "src/python/toolchain/github_integration/api/views_test.py:tests",
                                    "time": 4.3,
                                    "tests": [
                                        {"name": "test_resolve_ci", "time": 0.539, "outcome": "pass"},
                                        {"name": "test_resolve_ci_inactive_repo", "time": 0.272, "outcome": "pass"},
                                        {"name": "test_resolve_ci_key_too_long", "time": 0.472, "outcome": "pass"},
                                        {
                                            "name": "test_resolve_ci_fail_no_github_pr_info",
                                            "time": 0.534,
                                            "outcome": "pass",
                                        },
                                        {
                                            "name": "test_resolve_ci_fail_unknown_run_id",
                                            "time": 0.335,
                                            "outcome": "pass",
                                        },
                                        {"name": "test_resolve_ci_run_id_mismatch", "time": 0.41, "outcome": "pass"},
                                        {
                                            "name": "test_resolve_ci_fail_pr_parsing_error",
                                            "time": 0.383,
                                            "outcome": "pass",
                                        },
                                        {
                                            "name": "test_resolve_ci_fail_not_pull_request_event_env",
                                            "time": 0.248,
                                            "outcome": "pass",
                                        },
                                        {
                                            "name": "test_resolve_ci_fail_not_pull_request_event_workflow_run",
                                            "time": 0.442,
                                            "outcome": "pass",
                                        },
                                        {"name": "test_resolve_ci_fail_build_status", "time": 0.664, "outcome": "pass"},
                                    ],
                                },
                                {
                                    "name": "src.python.toolchain.github_integration.api.views_test.TestCIResolveViewGithubActions.test_resolve_ci_missing_env_vars",
                                    "test_file_path": "src/python/toolchain/github_integration/api/views_test.py:tests",
                                    "time": 1.92,
                                    "tests": [
                                        {"name": "missing0", "time": 0.245, "outcome": "pass"},
                                        {"name": "missing1", "time": 0.303, "outcome": "pass"},
                                        {"name": "missing2", "time": 0.26, "outcome": "pass"},
                                        {"name": "missing3", "time": 0.249, "outcome": "pass"},
                                        {"name": "missing4", "time": 0.241, "outcome": "pass"},
                                        {"name": "missing5", "time": 0.235, "outcome": "pass"},
                                        {"name": "missing6", "time": 0.385, "outcome": "pass"},
                                    ],
                                },
                                {
                                    "name": "src.python.toolchain.github_integration.api.views_test.TestCustomerRepoView",
                                    "test_file_path": "src/python/toolchain/github_integration/api/views_test.py:tests",
                                    "time": 0.48,
                                    "tests": [
                                        {"name": "test_get_repos", "time": 0.093, "outcome": "pass"},
                                        {
                                            "name": "test_get_repos_options_no_customer",
                                            "time": 0.028,
                                            "outcome": "pass",
                                        },
                                        {"name": "test_get_repos_options", "time": 0.101, "outcome": "pass"},
                                        {"name": "test_get_repos_options_no_repos", "time": 0.263, "outcome": "pass"},
                                    ],
                                },
                            ],
                            "timing": {"total": 20.54},
                            "target": "src/python/toolchain/github_integration/api/views_test.py:tests",
                            "outputs": {
                                "stdout": "redacted-because-too-large",
                                "stderr": "/Users/asher/.cache/pants/named_caches/pex_root/venvs/short/7f1e4dc7/lib/python3.8/site-packages/django/apps/registry.py:91: RemovedInDjango41Warning: 'django_prometheus' defines default_app_config = 'django_prometheus.apps.DjangoPrometheusConfig'. Django now detects this configuration automatically. You can remove default_app_config.\n  app_config = AppConfig.create(entry)\n",
                            },
                        },
                        {
                            "tests": [
                                {
                                    "name": "src.python.toolchain.github_integration.client.app_clients_test.TestRepoWebhookClient",
                                    "test_file_path": "src/python/toolchain/github_integration/client/app_clients_test.py:tests",
                                    "time": 0.13,
                                    "tests": [{"name": "test_post_github_webhook", "time": 0.133, "outcome": "pass"}],
                                }
                            ],
                            "timing": {"total": 0.13},
                            "target": "src/python/toolchain/github_integration/client/app_clients_test.py:tests",
                            "outputs": {
                                "stdout": "\x1b[1m============================= test session starts ==============================\x1b[0m\nplatform darwin -- Python 3.8.12, pytest-6.2.5, py-1.10.0, pluggy-1.0.0\nrootdir: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionSWtA5V\nplugins: responses-0.5.0, anyio-3.3.3, icdiff-0.5, django-4.4.0, cov-3.0.0, httpx-0.13.0\ncollected 1 item\n\nsrc/python/toolchain/github_integration/client/app_clients_test.py \x1b[32m.\x1b[0m\x1b[32m     [100%]\x1b[0m\n\n- generated xml file: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionSWtA5V/src.python.toolchain.github_integration.client.app_clients_test.py.tests.xml -\n\n\n\x1b[32m============================== \x1b[32m\x1b[1m1 passed\x1b[0m\x1b[32m in 4.14s\x1b[0m\x1b[32m ===============================\x1b[0m\n",
                                "stderr": "/Users/asher/.cache/pants/named_caches/pex_root/venvs/short/cb65cd13/lib/python3.8/site-packages/django/apps/registry.py:91: RemovedInDjango41Warning: 'django_prometheus' defines default_app_config = 'django_prometheus.apps.DjangoPrometheusConfig'. Django now detects this configuration automatically. You can remove default_app_config.\n  app_config = AppConfig.create(entry)\n",
                            },
                        },
                        {
                            "tests": [
                                {
                                    "name": "src.python.toolchain.github_integration.client.repo_clients_test.TestGithubRepoInfoClient",
                                    "test_file_path": "src/python/toolchain/github_integration/client/repo_clients_test.py:tests",
                                    "time": 0.72,
                                    "tests": [
                                        {"name": "test_get_pull_request_info", "time": 0.225, "outcome": "pass"},
                                        {
                                            "name": "test_get_pull_request_info_no_info",
                                            "time": 0.065,
                                            "outcome": "pass",
                                        },
                                        {"name": "test_get_commit_info", "time": 0.091, "outcome": "pass"},
                                        {"name": "test_get_commit_info_no_info", "time": 0.086, "outcome": "pass"},
                                        {"name": "test_get_push_info", "time": 0.061, "outcome": "pass"},
                                        {"name": "test_get_push_info_no_info", "time": 0.056, "outcome": "pass"},
                                        {"name": "test_resolve_ci_build", "time": 0.074, "outcome": "pass"},
                                        {"name": "test_resolve_ci_build_denied", "time": 0.065, "outcome": "pass"},
                                    ],
                                },
                                {
                                    "name": "src.python.toolchain.github_integration.client.repo_clients_test.TestGithubRepoInfoClient.test_get_pull_request_info_invalid_pr",
                                    "test_file_path": "src/python/toolchain/github_integration/client/repo_clients_test.py:tests",
                                    "time": 0.15,
                                    "tests": [
                                        {"name": "None", "time": 0.045, "outcome": "pass"},
                                        {"name": "0", "time": 0.066, "outcome": "pass"},
                                        {"name": "", "time": 0.044, "outcome": "pass"},
                                    ],
                                },
                                {
                                    "name": "src.python.toolchain.github_integration.client.repo_clients_test.TestGithubRepoInfoClient.test_get_commit_info_invalid_params",
                                    "test_file_path": "src/python/toolchain/github_integration/client/repo_clients_test.py:tests",
                                    "time": 0.47,
                                    "tests": [
                                        {"name": "None-None", "time": 0.092, "outcome": "pass"},
                                        {"name": "None-", "time": 0.09, "outcome": "pass"},
                                        {"name": "-", "time": 0.11, "outcome": "pass"},
                                        {"name": "puffy-", "time": 0.062, "outcome": "pass"},
                                        {"name": "-shirt", "time": 0.112, "outcome": "pass"},
                                    ],
                                },
                                {
                                    "name": "src.python.toolchain.github_integration.client.repo_clients_test.TestGithubRepoInfoClient.test_get_push_info_invalid_params",
                                    "test_file_path": "src/python/toolchain/github_integration/client/repo_clients_test.py:tests",
                                    "time": 0.38,
                                    "tests": [
                                        {"name": "None-None", "time": 0.063, "outcome": "pass"},
                                        {"name": "None-", "time": 0.071, "outcome": "pass"},
                                        {"name": "-", "time": 0.068, "outcome": "pass"},
                                        {"name": "puffy-", "time": 0.059, "outcome": "pass"},
                                        {"name": "-shirt", "time": 0.116, "outcome": "pass"},
                                    ],
                                },
                                {
                                    "name": "src.python.toolchain.github_integration.client.repo_clients_test.TestRepoWebhookClient",
                                    "test_file_path": "src/python/toolchain/github_integration/client/repo_clients_test.py:tests",
                                    "time": 0.28,
                                    "tests": [
                                        {"name": "test_get_webhook_secret", "time": 0.051, "outcome": "pass"},
                                        {"name": "test_post_github_webhook", "time": 0.093, "outcome": "pass"},
                                        {"name": "test_post_travis_webhook", "time": 0.074, "outcome": "pass"},
                                        {"name": "test_post_travis_webhook_404", "time": 0.064, "outcome": "pass"},
                                    ],
                                },
                                {
                                    "name": "src.python.toolchain.github_integration.client.repo_clients_test.TestGithubCustomerReposClient",
                                    "test_file_path": "src/python/toolchain/github_integration/client/repo_clients_test.py:tests",
                                    "time": 0.37,
                                    "tests": [
                                        {"name": "test_get_repos_empty", "time": 0.105, "outcome": "pass"},
                                        {"name": "test_get_repos", "time": 0.054, "outcome": "pass"},
                                        {"name": "test_get_install_info_no_installs", "time": 0.056, "outcome": "pass"},
                                        {"name": "test_get_install_info", "time": 0.152, "outcome": "pass"},
                                    ],
                                },
                            ],
                            "timing": {"total": 2.37},
                            "target": "src/python/toolchain/github_integration/client/repo_clients_test.py:tests",
                            "outputs": {
                                "stdout": "redacted-because-too-large",
                                "stderr": "/Users/asher/.cache/pants/named_caches/pex_root/venvs/short/cb65cd13/lib/python3.8/site-packages/django/apps/registry.py:91: RemovedInDjango41Warning: 'django_prometheus' defines default_app_config = 'django_prometheus.apps.DjangoPrometheusConfig'. Django now detects this configuration automatically. You can remove default_app_config.\n  app_config = AppConfig.create(entry)\n",
                            },
                        },
                        {
                            "tests": [
                                {
                                    "name": "src.python.toolchain.github_integration.hook_handlers.app_handlers_test.TestAppInstallEvents",
                                    "test_file_path": "src/python/toolchain/github_integration/hook_handlers/app_handlers_test.py:tests",
                                    "time": 4.78,
                                    "tests": [
                                        {
                                            "name": "test_install_app_created_missing_customer",
                                            "time": 1.897,
                                            "outcome": "pass",
                                        },
                                        {"name": "test_install_app_created", "time": 1.966, "outcome": "pass"},
                                        {
                                            "name": "test_install_app_reactivate_active",
                                            "time": 0.129,
                                            "outcome": "pass",
                                        },
                                        {
                                            "name": "test_install_app_reactivate_inactive",
                                            "time": 0.164,
                                            "outcome": "pass",
                                        },
                                        {
                                            "name": "test_install_app_reactivate_switch_customers",
                                            "time": 0.103,
                                            "outcome": "pass",
                                        },
                                        {"name": "test_delete_app_install", "time": 0.091, "outcome": "pass"},
                                        {
                                            "name": "test_delete_app_install_missing_customer",
                                            "time": 0.058,
                                            "outcome": "pass",
                                        },
                                        {
                                            "name": "test_install_app_slug_exists_on_different_customer",
                                            "time": 0.15,
                                            "outcome": "pass",
                                        },
                                        {"name": "test_install_app_slug_exists", "time": 0.123, "outcome": "pass"},
                                        {
                                            "name": "test_install_app_slug_exists_but_deactivated",
                                            "time": 0.101,
                                            "outcome": "pass",
                                        },
                                    ],
                                },
                                {
                                    "name": "src.python.toolchain.github_integration.hook_handlers.app_handlers_test.TestRepoInstallEvents",
                                    "test_file_path": "src/python/toolchain/github_integration/hook_handlers/app_handlers_test.py:tests",
                                    "time": 0.38,
                                    "tests": [
                                        {"name": "test_install_repo_removed", "time": 0.108, "outcome": "pass"},
                                        {
                                            "name": "test_install_repo_removed_invalid_install_id",
                                            "time": 0.267,
                                            "outcome": "pass",
                                        },
                                    ],
                                },
                            ],
                            "timing": {"total": 5.16},
                            "target": "src/python/toolchain/github_integration/hook_handlers/app_handlers_test.py:tests",
                            "outputs": {
                                "stdout": "\x1b[1m============================= test session starts ==============================\x1b[0m\nplatform darwin -- Python 3.8.12, pytest-6.2.5, py-1.10.0, pluggy-1.0.0\nrootdir: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionZ9AXGC\nplugins: responses-0.5.0, anyio-3.3.3, icdiff-0.5, django-4.4.0, cov-3.0.0, httpx-0.13.0\ncollected 12 items\n\nsrc/python/toolchain/github_integration/hook_handlers/app_handlers_test.py \x1b[32m.\x1b[0m\x1b[32m [  8%]\n\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m                                                              [100%]\x1b[0m\n\n- generated xml file: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionZ9AXGC/src.python.toolchain.github_integration.hook_handlers.app_handlers_test.py.tests.xml -\n\n\n\x1b[32m============================== \x1b[32m\x1b[1m12 passed\x1b[0m\x1b[32m in 8.66s\x1b[0m\x1b[32m ==============================\x1b[0m\n",
                                "stderr": "/Users/asher/.cache/pants/named_caches/pex_root/venvs/short/cb65cd13/lib/python3.8/site-packages/django/apps/registry.py:91: RemovedInDjango41Warning: 'django_prometheus' defines default_app_config = 'django_prometheus.apps.DjangoPrometheusConfig'. Django now detects this configuration automatically. You can remove default_app_config.\n  app_config = AppConfig.create(entry)\n",
                            },
                        },
                        {
                            "tests": [
                                {
                                    "name": "src.python.toolchain.github_integration.hook_handlers.repo_handlers_test.TestRepoWebhookHandlers",
                                    "test_file_path": "src/python/toolchain/github_integration/hook_handlers/repo_handlers_test.py:tests",
                                    "time": 10.46,
                                    "tests": [
                                        {"name": "test_pull_request_open", "time": 6.892, "outcome": "pass"},
                                        {"name": "test_pull_request_open_no_repo", "time": 0.605, "outcome": "pass"},
                                        {"name": "test_pull_request_assigned", "time": 0.395, "outcome": "pass"},
                                        {"name": "test_push_branch", "time": 0.438, "outcome": "pass"},
                                        {"name": "test_push_no_head", "time": 0.372, "outcome": "pass"},
                                        {"name": "test_push_tag", "time": 0.364, "outcome": "pass"},
                                        {"name": "test_change_run_not_github_action", "time": 0.353, "outcome": "pass"},
                                        {"name": "test_change_run_github_action", "time": 0.355, "outcome": "pass"},
                                        {
                                            "name": "test_change_run_github_action_missing_repo",
                                            "time": 0.687,
                                            "outcome": "pass",
                                        },
                                    ],
                                }
                            ],
                            "timing": {"total": 10.46},
                            "target": "src/python/toolchain/github_integration/hook_handlers/repo_handlers_test.py:tests",
                            "outputs": {
                                "stdout": "\x1b[1m============================= test session starts ==============================\x1b[0m\nplatform darwin -- Python 3.8.12, pytest-6.2.5, py-1.10.0, pluggy-1.0.0\nrootdir: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executiontq20Yi\nplugins: responses-0.5.0, anyio-3.3.3, icdiff-0.5, django-4.4.0, cov-3.0.0, httpx-0.13.0\ncollected 9 items\n\nsrc/python/toolchain/github_integration/hook_handlers/repo_handlers_test.py \x1b[32m.\x1b[0m\x1b[32m [ 11%]\n\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m                                                                 [100%]\x1b[0m\n\n- generated xml file: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executiontq20Yi/src.python.toolchain.github_integration.hook_handlers.repo_handlers_test.py.tests.xml -\n\n\n\x1b[32m============================== \x1b[32m\x1b[1m9 passed\x1b[0m\x1b[32m in 13.32s\x1b[0m\x1b[32m ==============================\x1b[0m\n",
                                "stderr": "/Users/asher/.cache/pants/named_caches/pex_root/venvs/short/c0babb84/lib/python3.8/site-packages/django/apps/registry.py:91: RemovedInDjango41Warning: 'django_prometheus' defines default_app_config = 'django_prometheus.apps.DjangoPrometheusConfig'. Django now detects this configuration automatically. You can remove default_app_config.\n  app_config = AppConfig.create(entry)\n",
                            },
                        },
                        {
                            "tests": [
                                {
                                    "name": "src.python.toolchain.github_integration.management.commands.add_repo_stats_fetch_test.TestAddRepoStatsFetchCommand",
                                    "test_file_path": "src/python/toolchain/github_integration/management/commands/add_repo_stats_fetch_test.py:tests",
                                    "time": 3.96,
                                    "tests": [{"name": "test_add_repo_stats_fetch", "time": 3.964, "outcome": "pass"}],
                                }
                            ],
                            "timing": {"total": 3.96},
                            "target": "src/python/toolchain/github_integration/management/commands/add_repo_stats_fetch_test.py:tests",
                            "outputs": {
                                "stdout": "\x1b[1m============================= test session starts ==============================\x1b[0m\nplatform darwin -- Python 3.8.12, pytest-6.2.5, py-1.10.0, pluggy-1.0.0\nrootdir: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionmijPK7\nplugins: responses-0.5.0, anyio-3.3.3, icdiff-0.5, django-4.4.0, cov-3.0.0, httpx-0.13.0\ncollected 1 item\n\nsrc/python/toolchain/github_integration/management/commands/add_repo_stats_fetch_test.py \x1b[32m.\x1b[0m\x1b[32m [100%]\x1b[0m\n\n- generated xml file: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionmijPK7/src.python.toolchain.github_integration.management.commands.add_repo_stats_fetch_test.py.tests.xml -\n\n\n\x1b[32m============================== \x1b[32m\x1b[1m1 passed\x1b[0m\x1b[32m in 6.28s\x1b[0m\x1b[32m ===============================\x1b[0m\n",
                                "stderr": "/Users/asher/.cache/pants/named_caches/pex_root/venvs/short/cb65cd13/lib/python3.8/site-packages/django/apps/registry.py:91: RemovedInDjango41Warning: 'django_prometheus' defines default_app_config = 'django_prometheus.apps.DjangoPrometheusConfig'. Django now detects this configuration automatically. You can remove default_app_config.\n  app_config = AppConfig.create(entry)\n",
                            },
                        },
                        {
                            "tests": [
                                {
                                    "name": "src.python.toolchain.github_integration.workers.github_repo_stats_test.TestGithubRepoStats",
                                    "test_file_path": "src/python/toolchain/github_integration/workers/github_repo_stats_test.py:tests",
                                    "time": 9.83,
                                    "tests": [
                                        {"name": "test_repeating_repo_stats_fetch", "time": 8.807, "outcome": "pass"},
                                        {"name": "test_one_off_repo_stats_fetch", "time": 0.538, "outcome": "pass"},
                                        {"name": "test_no_repo_id_found_case", "time": 0.485, "outcome": "pass"},
                                    ],
                                }
                            ],
                            "timing": {"total": 9.83},
                            "target": "src/python/toolchain/github_integration/workers/github_repo_stats_test.py:tests",
                            "outputs": {
                                "stdout": "\x1b[1m============================= test session starts ==============================\x1b[0m\nplatform darwin -- Python 3.8.12, pytest-6.2.5, py-1.10.0, pluggy-1.0.0\nrootdir: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionplAbyX\nplugins: responses-0.5.0, anyio-3.3.3, icdiff-0.5, django-4.4.0, cov-3.0.0, httpx-0.13.0\ncollected 3 items\n\nsrc/python/toolchain/github_integration/workers/github_repo_stats_test.py \x1b[32m.\x1b[0m\x1b[32m [ 33%]\n\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m                                                                       [100%]\x1b[0m\n\n- generated xml file: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionplAbyX/src.python.toolchain.github_integration.workers.github_repo_stats_test.py.tests.xml -\n\n\n\x1b[32m============================== \x1b[32m\x1b[1m3 passed\x1b[0m\x1b[32m in 12.54s\x1b[0m\x1b[32m ==============================\x1b[0m\n",
                                "stderr": "/Users/asher/.cache/pants/named_caches/pex_root/venvs/short/c1757a0e/lib/python3.8/site-packages/django/apps/registry.py:91: RemovedInDjango41Warning: 'django_prometheus' defines default_app_config = 'django_prometheus.apps.DjangoPrometheusConfig'. Django now detects this configuration automatically. You can remove default_app_config.\n  app_config = AppConfig.create(entry)\n",
                            },
                        },
                        {
                            "tests": [
                                {
                                    "name": "src.python.toolchain.github_integration.management.commands.deactivate_repo_test.TestDeactivateRepoCommand",
                                    "test_file_path": "src/python/toolchain/github_integration/management/commands/deactivate_repo_test.py:tests",
                                    "time": 4.36,
                                    "tests": [
                                        {"name": "test_deactivate_repo", "time": 3.716, "outcome": "pass"},
                                        {
                                            "name": "test_deactivate_repo_inactive_repo",
                                            "time": 0.647,
                                            "outcome": "pass",
                                        },
                                    ],
                                }
                            ],
                            "timing": {"total": 4.36},
                            "target": "src/python/toolchain/github_integration/management/commands/deactivate_repo_test.py:tests",
                            "outputs": {
                                "stdout": "\x1b[1m============================= test session starts ==============================\x1b[0m\nplatform darwin -- Python 3.8.12, pytest-6.2.5, py-1.10.0, pluggy-1.0.0\nrootdir: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionxOuuaA\nplugins: responses-0.5.0, anyio-3.3.3, icdiff-0.5, django-4.4.0, cov-3.0.0, httpx-0.13.0\ncollected 2 items\n\nsrc/python/toolchain/github_integration/management/commands/deactivate_repo_test.py \x1b[32m.\x1b[0m\x1b[32m [ 50%]\n\x1b[0m\x1b[32m.\x1b[0m\x1b[32m                                                                        [100%]\x1b[0m\n\n- generated xml file: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionxOuuaA/src.python.toolchain.github_integration.management.commands.deactivate_repo_test.py.tests.xml -\n\n\n\x1b[32m============================== \x1b[32m\x1b[1m2 passed\x1b[0m\x1b[32m in 6.67s\x1b[0m\x1b[32m ===============================\x1b[0m\n",
                                "stderr": "/Users/asher/.cache/pants/named_caches/pex_root/venvs/short/cb65cd13/lib/python3.8/site-packages/django/apps/registry.py:91: RemovedInDjango41Warning: 'django_prometheus' defines default_app_config = 'django_prometheus.apps.DjangoPrometheusConfig'. Django now detects this configuration automatically. You can remove default_app_config.\n  app_config = AppConfig.create(entry)\n",
                            },
                        },
                        {
                            "tests": [
                                {
                                    "name": "src.python.toolchain.github_integration.workers.configure_github_repo_test.TestGithubRepoConfigurator",
                                    "test_file_path": "src/python/toolchain/github_integration/workers/configure_github_repo_test.py:tests",
                                    "time": 5.73,
                                    "tests": [
                                        {"name": "test_unknown_repo", "time": 3.486, "outcome": "pass"},
                                        {"name": "test_create_webhook_no_hooks", "time": 0.406, "outcome": "pass"},
                                        {"name": "test_create_webhook_other_hooks", "time": 0.292, "outcome": "pass"},
                                        {"name": "test_delete_webhook_no_hooks", "time": 0.299, "outcome": "pass"},
                                        {
                                            "name": "test_delete_webhook_no_toolchain_hooks",
                                            "time": 0.399,
                                            "outcome": "pass",
                                        },
                                        {"name": "test_delete_webhook", "time": 0.33, "outcome": "pass"},
                                        {"name": "test_update_webhook", "time": 0.518, "outcome": "pass"},
                                    ],
                                }
                            ],
                            "timing": {"total": 5.73},
                            "target": "src/python/toolchain/github_integration/workers/configure_github_repo_test.py:tests",
                            "outputs": {
                                "stdout": "\x1b[1m============================= test session starts ==============================\x1b[0m\nplatform darwin -- Python 3.8.12, pytest-6.2.5, py-1.10.0, pluggy-1.0.0\nrootdir: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionr45x9M\nplugins: responses-0.5.0, anyio-3.3.3, icdiff-0.5, django-4.4.0, cov-3.0.0, httpx-0.13.0\ncollected 7 items\n\nsrc/python/toolchain/github_integration/workers/configure_github_repo_test.py \x1b[32m.\x1b[0m\x1b[32m [ 14%]\n\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m                                                                   [100%]\x1b[0m\n\n- generated xml file: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionr45x9M/src.python.toolchain.github_integration.workers.configure_github_repo_test.py.tests.xml -\n\n\n\x1b[32m============================== \x1b[32m\x1b[1m7 passed\x1b[0m\x1b[32m in 9.76s\x1b[0m\x1b[32m ===============================\x1b[0m\n",
                                "stderr": "/Users/asher/.cache/pants/named_caches/pex_root/venvs/short/cb65cd13/lib/python3.8/site-packages/django/apps/registry.py:91: RemovedInDjango41Warning: 'django_prometheus' defines default_app_config = 'django_prometheus.apps.DjangoPrometheusConfig'. Django now detects this configuration automatically. You can remove default_app_config.\n  app_config = AppConfig.create(entry)\n",
                            },
                        },
                    ]
                },
            }
        ]

    def test_extract_artifacts_with_action_digest(self, user: ToolchainUser, repo: Repo) -> None:
        run_info, build_data = self._load_fixture("remote_execution_failed", repo, user, stats_version="3")
        result = ProcessPantsData(run_info, ScmProvider.GITHUB).pipeline(build_data, None)
        assert result.has_metrics is True
