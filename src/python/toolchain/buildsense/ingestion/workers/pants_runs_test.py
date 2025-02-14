# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json

import pytest
from moto import mock_dynamodb, mock_s3

from toolchain.aws.s3 import S3
from toolchain.aws.test_utils.s3_utils import assert_bucket_empty, create_s3_bucket
from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.bitbucket_integration.client.repo_clients_test import add_bitbucket_push_response_for_repo
from toolchain.buildsense.ingestion.models import MoveBuild, ProcessPantsRun, ProcessQueuedBuilds
from toolchain.buildsense.ingestion.pants_data_ingestion import PantsDataIngestion
from toolchain.buildsense.ingestion.run_info_raw_store import RunInfoRawStore, WriteMode
from toolchain.buildsense.ingestion.run_info_table import RunInfoTable
from toolchain.buildsense.ingestion.views_api_test import (
    create_bitbucket_user_and_response,
    create_github_user_and_response,
)
from toolchain.buildsense.ingestion.workers.dispatcher import IngestionWorkDispatcher
from toolchain.buildsense.ingestion.workers.pants_runs import QueuedBuildsProcessor
from toolchain.buildsense.records.run_info import RunInfo
from toolchain.buildsense.test_utils.data_loader import get_fake_request_context, load_run_info
from toolchain.buildsense.test_utils.fixtures_loader import load_fixture
from toolchain.django.site.models import Customer, Repo, ToolchainUser
from toolchain.django.site.test_helpers.models_helpers import create_github_user
from toolchain.github_integration.client.repo_clients_test import (
    add_github_pr_response_for_repo,
    add_github_push_response_for_repo,
)
from toolchain.users.client.user_client_test import add_resolve_user_response_fail
from toolchain.workflow.models import WorkUnit
from toolchain.workflow.tests_helper import BaseWorkflowWorkerTests
from toolchain.workflow.work_dispatcher import WorkDispatcher


class BaseWorkerTests(BaseWorkflowWorkerTests):
    _BUCKET = "fake-test-buildsense-bucket"

    def get_dispatcher(self) -> type[WorkDispatcher]:
        return IngestionWorkDispatcher

    @pytest.fixture()
    def customer(self) -> Customer:
        return Customer.create(slug="ovaltine", name="Ovaltine!")

    @pytest.fixture()
    def user(self, customer: Customer) -> ToolchainUser:
        user = ToolchainUser.create(username="kenny", email="kenny@gold.com")
        customer.add_user(user)
        return user

    @pytest.fixture()
    def repo(self, customer: Customer) -> Repo:
        return Repo.create("goldjerry", customer=customer, name="Gold Jerry Gold")

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_dynamodb(), mock_s3():
            create_s3_bucket(self._BUCKET)
            RunInfoTable.create_table()
            yield

    def _prepare_build(self, user: ToolchainUser, repo: Repo, fixture: str) -> RunInfo:
        table = RunInfoTable.for_customer_id(repo.customer_id)
        assert ProcessPantsRun.objects.count() == 0
        pdi = PantsDataIngestion.for_repo(repo=repo)
        build_data = load_fixture(fixture)
        run_id = build_data["run_info"]["id"]
        now = utcnow()
        pdi.store_build_ended(
            build_stats=build_data,
            user=user,
            impersonated_user=None,
            request_ctx=get_fake_request_context(stats_version="3", request_id=f"req-{fixture}", accept_time=now),
        )
        run_info = table.get_by_run_id(repo_id=repo.pk, user_api_id=user.api_id, run_id=run_id)
        assert run_info is not None
        assert ProcessPantsRun.objects.count() == 1
        return run_info


class TestPantsRunProcessor(BaseWorkerTests):
    @pytest.fixture()
    def bitbucket_customer(self) -> Customer:
        return Customer.create(slug="moles", name="Moles", scm=Customer.Scm.BITBUCKET)

    @pytest.fixture()
    def bitbucket_repo(self, bitbucket_customer: Customer) -> Repo:
        return Repo.create("festivus", customer=bitbucket_customer, name="Festivus for the rest of us")

    @pytest.mark.parametrize(("fixture", "run_time"), [("sample3", 2.814), ("sample4", 3.291), ("sample5", 4.729)])
    def test_test_calculate_run_time(
        self, customer: Customer, repo: Repo, user: ToolchainUser, fixture: str, run_time: float
    ) -> None:
        table = RunInfoTable.for_customer_id(repo.customer_id)
        assert ProcessPantsRun.objects.count() == 0
        pdi = PantsDataIngestion.for_repo(repo=repo)
        build_data = load_fixture(fixture)
        run_id = build_data["run_info"]["id"]
        now = utcnow()
        pdi.store_build_ended(
            build_stats=build_data,
            user=user,
            impersonated_user=None,
            request_ctx=get_fake_request_context(stats_version="2", request_id=f"req-{fixture}", accept_time=now),
        )
        assert ProcessPantsRun.objects.count() == 1
        payload = ProcessPantsRun.objects.first()
        assert payload.repo_id == repo.pk
        assert payload.run_id == run_id
        assert payload.user_api_id == user.api_id
        stored_run = table.get_by_run_id(repo_id=repo.pk, user_api_id=user.api_id, run_id=run_id)
        assert stored_run.run_time is None
        assert self.do_work() == 1
        proceed_run = table.get_by_run_id(repo_id=repo.pk, user_api_id=user.api_id, run_id=run_id)
        assert proceed_run.run_time == datetime.timedelta(seconds=run_time)

    def test_create_zipkin_trace_files(self, user: ToolchainUser, repo: Repo) -> None:
        run_info = self._prepare_build(user, repo, "build_end_workunits_v3")
        store = RunInfoRawStore.for_repo(repo=repo)
        assert store.get_named_data(run_info, "final.json") is not None
        assert store.get_named_data(run_info, "zipkin_trace.json") is None
        assert self.do_work() == 1
        zipkin_trace_file = store.get_named_data(run_info, "zipkin_trace.json")
        assert zipkin_trace_file is not None
        assert json.loads(zipkin_trace_file.content) == load_fixture("zipkin_trace_1")

    def test_extract_artifacts(self, user: ToolchainUser, repo: Repo) -> None:
        self._prepare_build(user, repo, "black_fmt_with_artifacts")
        assert self.do_work() == 1
        wu = ProcessPantsRun.objects.first().work_unit
        assert wu.state == WorkUnit.SUCCEEDED
        s3 = S3()
        key_base = f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.id}/{user.api_id}/pants_run_2020_08_04_16_35_47_594_12a3fafc99bc4f9f81d1c92e2fcc7b75"
        assert s3.exists("fake-test-buildsense-bucket", f"{key_base}/zipkin_trace.json") is True
        assert s3.exists("fake-test-buildsense-bucket", f"{key_base}/artifacts_work_units.json") is True
        assert s3.exists("fake-test-buildsense-bucket", f"{key_base}/fmt_84ecd738a862391f_artifacts.json") is True
        artifacts = json.loads(s3.get_content("fake-test-buildsense-bucket", f"{key_base}/artifacts_work_units.json"))
        assert artifacts == {
            "pants_options": [
                {
                    "artifacts": "pants_options.json",
                    "description": "Pants Options",
                    "name": "pants_options",
                    "content_types": ["pants_options"],
                },
            ],
            "fmt": [
                {
                    "work_unit_id": "36be844a11cbad03",
                    "name": "pants.backend.python.lint.black.rules.black_fmt",
                    "description": "Format using Black",
                    "artifacts": "fmt_84ecd738a862391f_artifacts.json",
                    "content_types": ["text/plain"],
                }
            ],
        }

    def test_reprocess_extract_artifacts(self, user: ToolchainUser, repo: Repo) -> None:
        self._prepare_build(user, repo, "black_fmt_with_artifacts")
        s3 = S3()
        key_base = f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.id}/{user.api_id}/pants_run_2020_08_04_16_35_47_594_12a3fafc99bc4f9f81d1c92e2fcc7b75"

        s3.upload_json_str(
            bucket="fake-test-buildsense-bucket",
            key=f"{key_base}/artifacts_work_units.json",
            json_str=json.dumps(
                {
                    "test": [
                        {
                            "artifacts": "ugly_baby.json",
                            "description": "Run Pytest",
                            "name": "pants.backend.python.goals.pytest_runner.run_python_test",
                            "work_unit_id": "babfb4e77a0d0a9a",
                        },
                        {
                            "artifacts": "it_moved.json",
                            "description": "Run Pytest",
                            "name": "pants.backend.python.goals.pytest_runner.run_python_test",
                            "work_unit_id": "1447079bef259506",
                        },
                    ]
                }
            ),
        )
        s3.upload_content(
            bucket="fake-test-buildsense-bucket",
            key=f"{key_base}/it_moved.json",
            content_bytes=b"I've got a flash for you joy-boy",
        )
        s3.upload_content(
            bucket="fake-test-buildsense-bucket", key=f"{key_base}/ugly_baby.json", content_bytes=b"Look like stalin"
        )
        assert self.do_work() == 1
        wu = ProcessPantsRun.objects.first().work_unit
        assert wu.state == WorkUnit.SUCCEEDED
        assert s3.exists("fake-test-buildsense-bucket", f"{key_base}/it_moved.json") is False
        assert s3.exists("fake-test-buildsense-bucket", f"{key_base}/ugly_baby.json") is False
        assert s3.exists("fake-test-buildsense-bucket", f"{key_base}/zipkin_trace.json") is True
        wu = json.loads(s3.get_content("fake-test-buildsense-bucket", f"{key_base}/artifacts_work_units.json"))
        assert wu == {
            "pants_options": [
                {
                    "artifacts": "pants_options.json",
                    "description": "Pants Options",
                    "name": "pants_options",
                    "content_types": ["pants_options"],
                },
            ],
            "fmt": [
                {
                    "work_unit_id": "36be844a11cbad03",
                    "name": "pants.backend.python.lint.black.rules.black_fmt",
                    "description": "Format using Black",
                    "artifacts": "fmt_84ecd738a862391f_artifacts.json",
                    "content_types": ["text/plain"],
                }
            ],
        }
        updated_content = json.loads(
            s3.get_content("fake-test-buildsense-bucket", f"{key_base}/fmt_84ecd738a862391f_artifacts.json")
        )
        assert isinstance(updated_content, list)
        assert len(updated_content) == 1
        assert updated_content[0]["content"] == "All done! ✨ 🍰 ✨\n34 files left unchanged.\n"

    def _prepare_scm_integration_responses_for_push(
        self, httpx_mock, user: ToolchainUser, repo: Repo, customer: Customer, commit_sha: str
    ) -> ToolchainUser:
        add_github_push_response_for_repo(
            httpx_mock,
            repo,
            branch="master",
            commit_sha=commit_sha,
            fixture="repo_push",
        )

        return create_github_user_and_response(
            httpx_mock, customer, username="benjy", github_username="benjyw", github_user_id="512764"
        )

    def test_reprocess_extract_artifacts_no_artifacts(self, httpx_mock, user: ToolchainUser, repo: Repo) -> None:
        add_github_push_response_for_repo(
            httpx_mock, repo, branch="master", commit_sha="ccc7519fcf606b2d7f719e55649706edc683c5c5"
        )
        self._prepare_build(user, repo, "test_no_artifacts")
        s3 = S3()
        key_base = f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.id}/{user.api_id}/pants_run_2020_09_24_23_21_05_978_e7ae7e687ade4ea293368c26c374a22f"
        s3.upload_json_str(
            bucket="fake-test-buildsense-bucket",
            key=f"{key_base}/artifacts_work_units.json",
            json_str=json.dumps(
                {
                    "test": [
                        {
                            "work_unit_id": "98fcff0506343839",
                            "name": "pants.backend.python.goals.pytest_runner.run_python_test",
                            "description": "Run Pytest",
                            "artifacts": "non_existent_file.json",
                        }
                    ]
                }
            ),
        )

        assert self.do_work() == 1
        wu = ProcessPantsRun.objects.first().work_unit
        assert wu.state == WorkUnit.SUCCEEDED
        assert s3.exists("fake-test-buildsense-bucket", f"{key_base}/non_existent_file.json") is False

    def test_extract_artifacts_with_log(self, user: ToolchainUser, repo: Repo) -> None:
        self._prepare_build(user, repo, "black_fmt_with_artifacts")
        s3 = S3()
        key_base = f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.id}/{user.api_id}/pants_run_2020_08_04_16_35_47_594_12a3fafc99bc4f9f81d1c92e2fcc7b75"
        s3.upload_content(
            bucket=self._BUCKET,
            key=f"{key_base}/pants_run_log.txt",
            content_type="text/plain",
            content_bytes=b"No one carries a wallet anymore, they went out with powdered wigs",
        )
        assert self.do_work() == 1
        wu = ProcessPantsRun.objects.first().work_unit
        assert wu.state == WorkUnit.SUCCEEDED
        assert s3.exists("fake-test-buildsense-bucket", f"{key_base}/zipkin_trace.json") is True
        assert s3.exists("fake-test-buildsense-bucket", f"{key_base}/artifacts_work_units.json") is True
        assert s3.exists("fake-test-buildsense-bucket", f"{key_base}/fmt_84ecd738a862391f_artifacts.json") is True
        artifacts = json.loads(s3.get_content("fake-test-buildsense-bucket", f"{key_base}/artifacts_work_units.json"))
        assert artifacts == {
            "pants_options": [
                {
                    "artifacts": "pants_options.json",
                    "description": "Pants Options",
                    "name": "pants_options",
                    "content_types": ["pants_options"],
                },
            ],
            "fmt": [
                {
                    "work_unit_id": "36be844a11cbad03",
                    "name": "pants.backend.python.lint.black.rules.black_fmt",
                    "description": "Format using Black",
                    "artifacts": "fmt_84ecd738a862391f_artifacts.json",
                    "content_types": ["text/plain"],
                }
            ],
            "logs": [
                {
                    "name": "Logs",
                    "description": "Pants run log",
                    "artifacts": "pants_run_log.txt",
                    "content_types": ["text/plain"],
                }
            ],
        }

    def test_lint_from_bitbucket_pipelines_ci_branch(
        self, user: ToolchainUser, bitbucket_customer: Customer, bitbucket_repo: Repo, httpx_mock
    ) -> None:
        bitbucket_customer.add_user(user)
        add_bitbucket_push_response_for_repo(
            httpx_mock,
            bitbucket_repo,
            ref_type="branch",
            ref_name="main",
            commit_sha="2a28689353cf6f6dc72f03942c906ca6347d6dfe",
            fixture="repo_push_create_branch",
        )
        ci_user = create_bitbucket_user_and_response(
            httpx_mock=httpx_mock,
            customer=bitbucket_customer,
            username="tinsel",
            bitbucket_username="asherf",
            bitbucket_user_id="6059303e630024006fab8c2b",
        )
        self._prepare_build(ci_user, bitbucket_repo, "bitbucket_branch_lint_run")
        assert self.do_work() == 1
        wu = ProcessPantsRun.objects.first().work_unit
        assert wu.state == WorkUnit.SUCCEEDED

    def test_lint_from_bitbucket_pipelines_ci_tag(
        self, user: ToolchainUser, bitbucket_customer: Customer, bitbucket_repo: Repo, httpx_mock
    ) -> None:
        bitbucket_customer.add_user(user)
        add_bitbucket_push_response_for_repo(
            httpx_mock,
            bitbucket_repo,
            ref_type="tag",
            ref_name="h&h-bagles",
            commit_sha="113feb0671944c44d274fc4d7c32c681427f9011",
            fixture="repo_push_create_tag",
        )
        ci_user = create_bitbucket_user_and_response(
            httpx_mock=httpx_mock,
            customer=bitbucket_customer,
            username="tinsel",
            bitbucket_username="asherf",
            bitbucket_user_id="6059303e630024006fab8c2b",
        )
        self._prepare_build(ci_user, bitbucket_repo, "bitbucket_tag_lint_run")
        assert self.do_work() == 1
        wu = ProcessPantsRun.objects.first().work_unit
        assert wu.state == WorkUnit.SUCCEEDED

    def test_with_calculate_indicators(self, httpx_mock, customer: Customer, repo: Repo) -> None:
        github_user = create_github_user_and_response(
            httpx_mock, customer=customer, username="george", github_user_id="512764", github_username="glc"
        )
        customer.add_user(github_user)
        add_github_push_response_for_repo(
            httpx_mock,
            repo=repo,
            branch="pants2.7",
            commit_sha="88953130e514d27fe5c0d6ab013931511d44374c",
            fixture="repo_push",
        )
        old_run_info = self._prepare_build(github_user, repo, "typecheck_run_with_cache_counters")
        assert old_run_info.indicators is None
        assert self.do_work() == 1
        wu = ProcessPantsRun.objects.first().work_unit
        assert wu.state == WorkUnit.SUCCEEDED

        updated_run_info = RunInfoTable.for_customer_id(customer_id=customer.id).get_by_run_id(
            repo_id=repo.id, user_api_id=github_user.api_id, run_id=old_run_info.run_id
        )
        assert updated_run_info.indicators == {
            "used_cpu_time": 73558,
            "saved_cpu_time_local": 0,
            "saved_cpu_time_remote": 970,
            "saved_cpu_time": 970,
            "hits": 8,
            "total": 4,
            "hit_fraction": 2.0,
            "hit_fraction_local": 1,
            "hit_fraction_remote": 1,
        }
        assert updated_run_info.title == "Update ./pants runner script. (#6600)"
        assert updated_run_info.ci_info is not None
        assert updated_run_info.ci_info.build_url == "https://circleci.com/gh/toolchainlabs/toolchain/106354"

    def test_deleted_build(self, user: ToolchainUser, repo: Repo) -> None:
        run_info = load_run_info("build_end_workunits_v3", repo, user)
        ppr = ProcessPantsRun.create(run_info, repo=repo)
        ppr.mark_as_deleted()
        assert self.do_work() == 1
        loaded_ppr = ProcessPantsRun.objects.first()
        assert loaded_ppr.work_unit.state == WorkUnit.SUCCEEDED

    def test_with_different_ci_info(self, httpx_mock, user: ToolchainUser, repo: Repo, customer: Customer) -> None:
        add_github_push_response_for_repo(  # TODO: should force timeout error for request
            httpx_mock, repo, branch="master", commit_sha="ccc7519fcf606b2d7f719e55649706edc683c5c5"
        )
        self._prepare_build(user, repo, "test_no_artifacts")
        ci_user = self._prepare_scm_integration_responses_for_push(
            httpx_mock, user, repo, customer, "ccc7519fcf606b2d7f719e55649706edc683c5c5"
        )

        s3 = S3()
        key_base = f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.id}/{user.api_id}/pants_run_2020_09_24_23_21_05_978_e7ae7e687ade4ea293368c26c374a22f"
        s3.upload_json_str(
            bucket="fake-test-buildsense-bucket",
            key=f"{key_base}/artifacts_work_units.json",
            json_str=json.dumps(
                {
                    "test": [
                        {
                            "work_unit_id": "98fcff0506343839",
                            "name": "pants.backend.python.goals.pytest_runner.run_python_test",
                            "description": "Run Pytest",
                            "artifacts": "non_existent_file.json",
                        }
                    ]
                }
            ),
        )

        assert self.do_work() == 1
        assert s3.exists("fake-test-buildsense-bucket", f"{key_base}/non_existent_file.json") is False
        loaded_ppr = ProcessPantsRun.objects.first()
        assert loaded_ppr.work_unit.state == WorkUnit.PENDING
        reqs = list(loaded_ppr.work_unit.requirements.all())
        assert len(reqs) == 1
        assert MoveBuild.objects.count() == 1
        move_build = MoveBuild.objects.first()
        assert reqs[0].id == move_build.work_unit_id
        assert move_build.repo_id == repo.id
        assert move_build.run_id == "pants_run_2020_09_24_23_21_05_978_e7ae7e687ade4ea293368c26c374a22f"
        assert move_build.from_user_api_id == user.api_id
        assert move_build.to_user_api_id == loaded_ppr.user_api_id == ci_user.api_id


class TestQueuedBuildsProcessor(BaseWorkerTests):
    def _upload_builds(self, user_api_id: str, repo: Repo) -> None:
        json_build_data = {
            "customer_id": repo.customer_id,
            "repo_id": repo.id,
            "user_api_id": user_api_id,
            "accepted_time": utcnow().isoformat(),
            "node_id": "bosco",
            "request_id": "feats-of-strength",
            "builds": {
                name: load_fixture(name) for name in ("sample_10_finish", "sample_9_end", "ci_build_pr_final_1")
            },
        }
        S3().upload_json_str(
            bucket=self._BUCKET,
            key="bad-chicken/mess-u-up/jerry/queued_build_1.json",
            json_str=json.dumps(json_build_data),
        )

    def test_invalid_repo_id(self, customer: Customer) -> None:
        payload = ProcessQueuedBuilds.objects.create(
            repo_id="festivus", bucket=self._BUCKET, key="blabla", num_of_builds=3
        )
        worker = QueuedBuildsProcessor()
        with pytest.raises(ToolchainAssertion, match="Could not load repo for"):
            worker.do_work(payload)

    def test_process_queue_builds(self, httpx_mock, user: ToolchainUser, repo: Repo) -> None:
        self._upload_builds(user.api_id, repo)
        add_github_pr_response_for_repo(httpx_mock, repo, 6490, "pull_request_review_requested")
        add_resolve_user_response_fail(httpx_mock, user=user, customer_id=repo.customer_id, github_user_id="1268088")
        payload = ProcessQueuedBuilds.create(
            repo, self._BUCKET, key="bad-chicken/mess-u-up/jerry/queued_build_1.json", num_of_builds=3
        )
        worker = QueuedBuildsProcessor()
        assert ProcessPantsRun.objects.count() == 0
        assert worker.do_work(payload) is True
        assert ProcessPantsRun.objects.count() == 3
        table = RunInfoTable.for_customer_id(repo.customer_id)
        run_infos = [
            table.get_by_run_id(
                repo_id=repo.id,
                user_api_id=user.api_id,
                run_id="pants_run_2020_01_28_17_50_13_106_c4c0a8c0235447a49facd0f338cce581",
            ),
            table.get_by_run_id(
                repo_id=repo.id,
                user_api_id=user.api_id,
                run_id="pants_run_2020_01_23_11_41_55_931_68189fba67f94d7ebd9b119f4966124c",
            ),
            table.get_by_run_id(
                repo_id=repo.id,
                user_api_id=user.api_id,
                run_id="pants_run_2020_08_13_00_21_00_240_87ceaef8db824ad9ac25fa866e988427",
            ),
        ]
        s3 = S3()
        for ri in run_infos:
            assert ri.server_info.request_id == "feats-of-strength"
            assert ri.server_info.s3_bucket == "fake-test-buildsense-bucket"
            assert ri.customer_id == repo.customer_id
            assert ri.repo_id == repo.id
            assert ri.user_api_id == user.api_id
            assert s3.exists(bucket=self._BUCKET, key=ri.server_info.s3_key) is True


class TestBuilderMover(BaseWorkerTests):
    def test_move_build(self, user: ToolchainUser, repo: Repo, customer: Customer) -> None:
        target_user = create_github_user("cosmo", github_user_id="662772", github_username="kramer")
        customer.add_user(target_user)
        run_info = self._prepare_build(user, repo, "black_fmt_with_artifacts")
        store = RunInfoRawStore.for_repo(repo)
        store.save_build_json_file(
            run_id=run_info.run_id,
            json_bytes_or_file=json.dumps({"soup": "no soup for you"}).encode(),
            name="jerry",
            user_api_id=user.api_id,
            mode=WriteMode.OVERWRITE,
            dry_run=False,
            is_compressed=False,
            metadata={"dinner": "No way wine is better than Pepsi!"},
        )
        ProcessPantsRun.objects.get(run_id=run_info.run_id).work_unit.delete()
        MoveBuild.create(run_info, to_user_api_id=target_user.api_id)
        assert self.do_work() == 1
        wu = MoveBuild.objects.first().work_unit
        assert wu.state == WorkUnit.SUCCEEDED
        table = RunInfoTable.for_customer_id(customer_id=customer.id)
        assert table.get_by_run_id(repo_id=repo.id, user_api_id=user.api_id, run_id=run_info.run_id) is None
        updated_run_info = table.get_by_run_id(repo_id=repo.id, user_api_id=target_user.api_id, run_id=run_info.run_id)
        assert updated_run_info is not None
        assert updated_run_info.user_api_id == target_user.api_id
        si = updated_run_info.server_info
        assert (
            si.s3_key
            == f"no-soup-for-you/buildsense/storage/{customer.id}/{repo.id}/{target_user.api_id}/{run_info.run_id}/final.json"
        )
        s3 = S3()
        assert_bucket_empty(
            s3, self._BUCKET, f"no-soup-for-you/buildsense/storage/{customer.id}/{repo.id}/{user.api_id}/"
        )
        keys = s3.keys_with_prefix(
            bucket=self._BUCKET,
            key_prefix=f"no-soup-for-you/buildsense/storage/{customer.id}/{repo.id}/{target_user.api_id}/",
        )
        other_key = f"no-soup-for-you/buildsense/storage/{customer.id}/{repo.id}/{target_user.api_id}/{run_info.run_id}/jerry.json"
        assert set(keys) == {si.s3_key, other_key}
        bf = store.get_named_data(updated_run_info, name="jerry.json", optional=False)
        assert bf is not None
        assert json.loads(bf.content) == {"soup": "no soup for you"}
        assert bf.content_type == "application/json"
        assert bf.metadata == {"dinner": "No way wine is better than Pepsi!"}
