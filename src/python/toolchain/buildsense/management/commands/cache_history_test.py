# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import re

import pytest
from moto import mock_dynamodb, mock_s3

from toolchain.aws.test_utils.s3_utils import create_s3_bucket
from toolchain.base.datetime_tools import utcnow
from toolchain.buildsense.ingestion.pants_data_ingestion import PantsDataIngestion
from toolchain.buildsense.ingestion.run_info_raw_store import RunInfoRawStore
from toolchain.buildsense.ingestion.run_info_table import RunInfoTable
from toolchain.buildsense.management.commands.cache_history import Command
from toolchain.buildsense.records.run_info import RunInfo, ServerInfo
from toolchain.buildsense.test_utils.data_loader import insert_build_data
from toolchain.buildsense.test_utils.fixtures_loader import load_fixture
from toolchain.django.site.models import Customer, Repo, ToolchainUser
from toolchain.django.site.test_helpers.models_helpers import create_github_user
from toolchain.util.test.elastic_search_util import DummyElasticRequests


@pytest.mark.django_db()
class BaseTestCommand:
    _BUCKET = "fake-test-buildsense-bucket"

    @pytest.fixture()
    def customer(self) -> Customer:
        return Customer.create(slug="acmeid", name="acme")

    @pytest.fixture()
    def user(self, customer: Customer) -> ToolchainUser:
        user = create_github_user(
            username="kramer", email="kramer@jerrysplace.com", full_name="Cosmo Kramer", github_user_id="10109"
        )
        customer.add_user(user)
        return user

    @pytest.fixture(autouse=True)
    def repo(self, customer: Customer) -> Repo:
        return Repo.create("acmebotid", customer=customer, name="acmebot")

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_dynamodb(), mock_s3():
            create_s3_bucket(self._BUCKET)
            RunInfoTable.create_table()
            yield

    @pytest.fixture(autouse=True)
    def _es_mock(self):
        DummyElasticRequests.reset()

    def _store_build(
        self,
        repo: Repo,
        user: ToolchainUser,
        build_data: dict,
        build_time: datetime.datetime,
    ) -> RunInfo:
        pdi = PantsDataIngestion.for_repo(repo)
        store = RunInfoRawStore.for_repo(repo=repo)
        run_id = build_data["run_info"]["id"]
        dummy_server_info = ServerInfo(
            request_id="test",
            accept_time=build_time,
            stats_version="1",
            environment="jambalaya",
            s3_bucket=self._BUCKET,
            s3_key=f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.pk}/{user.api_id}/{run_id}/final.json",
        )
        created, run_info = insert_build_data(pdi, build_data, user, dummy_server_info)
        assert created is True
        store.save_final_build_stats(run_id=run_id, build_stats=build_data, user_api_id=user.api_id)
        return run_info

    def _seed_dynamodb_data(
        self, repo: Repo, *users: ToolchainUser, build_time: datetime.datetime | None = None
    ) -> list[RunInfo]:
        build_time = (build_time or utcnow()) - datetime.timedelta(minutes=3)

        run_infos = []

        fixtures_and_users = [
            (load_fixture(f"sample{fixture_id}"), users[(fixture_id - 1) % len(users)]) for fixture_id in range(1, 7)
        ]
        fixtures_and_users.extend(
            [(load_fixture("ci_build_branch_final_1"), users[0]), (load_fixture("ci_build_pr_final_1"), users[0])]
        )
        for build_data, user in fixtures_and_users:
            build_time -= datetime.timedelta(hours=1)
            build_data["run_info"].pop("repo_id", None)
            build_data["run_info"]["timestamp"] = int(build_time.replace(tzinfo=datetime.timezone.utc).timestamp())
            run_info = self._store_build(repo, user, build_data, build_time)
            run_infos.append(run_info)
        DummyElasticRequests.add_search_response(run_infos)
        return run_infos


class FakeCommand(Command):
    def __init__(self, *args, **kwargs) -> None:
        self.calls: list[tuple[int, str, str, str, str]] = []
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        raise AssertionError("This code is for unit test only")

    def _render_match(self, start_usecs: int, user: str, run_id: str, source: str, definition: str) -> None:
        self.calls.append((start_usecs, user, run_id, source, definition))


class TestCacheHistoryCommand(BaseTestCommand):
    def test_single_match(self, repo: Repo, user: ToolchainUser) -> None:
        self._seed_dynamodb_data(repo, user)
        cmd = FakeCommand()
        cmd.render_history(
            repo,
            "master",
            re.compile("Searching for `tar`"),
            0,
            100000,
            datetime.datetime(2019, 1, 1, tzinfo=datetime.timezone.utc),
        )
        assert len(cmd.calls) == 1
        assert (
            1597425452770587,
            "toolchain",
            "pants_run_2020_08_14_17_17_32_751_5263973c8e154a7fb3d8f98232dd24f2",
            "RanLocally",
        ) == cmd.calls[0][:4]
