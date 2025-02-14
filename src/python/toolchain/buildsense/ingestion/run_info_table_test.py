# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import base64
import datetime
import json
from collections.abc import Sequence
from types import GeneratorType

import pytest
from moto import mock_dynamodb

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import InvalidCursorError, ToolchainAssertion
from toolchain.buildsense.ingestion.pants_data_ingestion import PantsDataIngestion
from toolchain.buildsense.ingestion.run_info_table import RunInfoTable
from toolchain.buildsense.records.run_info import CIDetails, RunInfo, ServerInfo
from toolchain.buildsense.search.run_info_search_index import RunKey
from toolchain.buildsense.test_utils.data_loader import insert_build_data, load_run_info, parse_run_info
from toolchain.buildsense.test_utils.fixtures_loader import load_fixture
from toolchain.buildsense.test_utils.table_utils import get_table_items, get_table_items_count
from toolchain.django.site.models import Customer, Repo, ToolchainUser


@pytest.mark.django_db()
class BaseRunInfoTableTests:
    @pytest.fixture()
    def user(self):
        user = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        Customer.create(slug="jerry", name="Jerry Seinfeld Inc").add_user(user)
        return user

    @pytest.fixture()
    def repo(self, user: ToolchainUser) -> Repo:
        customer = user.customers.first()
        return Repo.create("funnyguy", customer=customer, name="Jerry Seinfeld is a funny guy")

    @pytest.fixture()
    def table(self, repo: Repo) -> Repo:
        table = RunInfoTable.for_customer_id(repo.customer_id)
        table._allow_missing_keys_in_tests = True
        return table

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_dynamodb():
            RunInfoTable.create_table()
            yield

    @classmethod
    def _get_server_info(
        cls, repo: Repo, user: ToolchainUser, run_id: str, accept_time: datetime.datetime, modifier: str | None = None
    ) -> ServerInfo:
        return ServerInfo(
            request_id=f"test-{modifier or ''}",
            accept_time=accept_time,
            stats_version="1",
            environment="crab/bisque",
            s3_bucket="fake-test-buildsense-bucket",
            s3_key=f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.id}/{user.api_id}/{run_id}/final.json",
        )

    @classmethod
    def seed_dynamodb_data(
        cls,
        repo: Repo,
        user: ToolchainUser,
        base_time: datetime.datetime,
        delta: datetime.timedelta | None = None,
        modifier: str | None = None,
        run_id_prefix: str | None = None,
        fixtures: Sequence[str] = tuple(),
    ) -> tuple[str, ...]:
        base_time = base_time or utcnow()
        delta = delta or datetime.timedelta(minutes=3)
        build_time = base_time
        run_ids = []
        fixtures = fixtures or [f"sample{fixture_id}" for fixture_id in range(1, 7)]
        pdi = PantsDataIngestion.for_repo(repo)
        for fixture_id, fixture_name in enumerate(fixtures):
            build_data = load_fixture(fixture_name)
            server_info = cls._get_server_info(repo, user, build_data["run_info"]["id"], base_time, modifier)
            run_id = cls._insert_data(
                pdi, user, build_data, modifier, fixture_id + 1, run_id_prefix, build_time, server_info
            )
            build_time = build_time + delta
            run_ids.append(run_id)
        return tuple(run_ids)

    @classmethod
    def _insert_data(
        cls,
        pdi: PantsDataIngestion,
        user: ToolchainUser,
        build_data: dict,
        modifier: str | None,
        fixture_id: int,
        run_id_prefix: str | None,
        build_time: datetime.datetime,
        server_info: ServerInfo,
    ) -> str:
        run_info = build_data["run_info"]
        run_info.pop("repo_id", None)
        run_info["branch"] = str(fixture_id)
        if modifier:
            run_info["buildroot"] = modifier
        if run_id_prefix:
            run_info["id"] = run_id_prefix + run_info["id"]
        run_info["timestamp"] = int(build_time.replace(tzinfo=datetime.timezone.utc).timestamp())
        created, _ = insert_build_data(pdi, build_data, user, server_info)
        assert created is True
        return run_info["id"]

    def _insert_ci_build(
        self, user: ToolchainUser, repo: Repo, fixture_name: str, modifier: str | None, base_time: datetime.datetime
    ):
        build_stats = load_fixture(fixture_name)
        server_info = self._get_server_info(repo, user, build_stats["run_info"]["id"], base_time, modifier)
        pdi = PantsDataIngestion.for_repo(repo)
        run_info = parse_run_info(fixture_data=build_stats, repo=repo, user=user, server_info=server_info)
        pdi._table.save_run(run_info)


class TestRunInfoTableGetData(BaseRunInfoTableTests):
    def test_str(self, repo: Repo, user: ToolchainUser) -> None:
        table = RunInfoTable.for_customer_id(repo.customer_id)
        assert str(table) == f"RunInfoTable(customer_id={repo.customer_id} environment=test)"

    def test_bad_queries(self, repo: Repo, user: ToolchainUser) -> None:
        now = utcnow()
        table = RunInfoTable.for_customer_id(repo.customer_id)
        with pytest.raises(ToolchainAssertion, match="Earliest must be before or equal to latest"):
            table.get_user_repo_builds(
                repo_id=repo.pk, user_api_id=user.api_id, latest=now - datetime.timedelta(days=4)
            )

        with pytest.raises(ToolchainAssertion, match="Earliest must be before or equal to latest"):
            table.get_user_repo_builds(
                repo_id=repo.pk, user_api_id=user.api_id, earliest=now + datetime.timedelta(minutes=3)
            )

        with pytest.raises(ToolchainAssertion, match="Earliest must be before or equal to latest"):
            table.get_user_repo_builds(
                repo_id=repo.pk,
                user_api_id=user.api_id,
                earliest=now - datetime.timedelta(minutes=30),
                latest=now - datetime.timedelta(minutes=50),
            )

    def test_get_build_with_ci_info(self, repo: Repo, user: ToolchainUser) -> None:
        base_time = utcnow() - datetime.timedelta(minutes=80)
        self._insert_ci_build(user, repo, "ci_build_pr_final_1", "tinsel", base_time)
        table = RunInfoTable.for_customer_id(repo.customer_id)
        run_info = table.get_by_run_id(
            repo_id=repo.pk,
            user_api_id=user.api_id,
            run_id="pants_run_2020_08_13_00_21_00_240_87ceaef8db824ad9ac25fa866e988427",
        )
        assert run_info.version == "2.0.0.dev6"
        assert run_info.outcome == "SUCCESS"
        assert run_info.run_id == "pants_run_2020_08_13_00_21_00_240_87ceaef8db824ad9ac25fa866e988427"
        assert run_info.ci_info.run_type == CIDetails.Type.PULL_REQUEST
        assert run_info.ci_info.pull_request == 6490
        assert run_info.ci_info.job_name == "build"
        assert run_info.ci_info.username == "asherf"
        assert run_info.ci_info.build_url == "https://circleci.com/gh/toolchainlabs/toolchain/22579"
        assert run_info.ci_info.build_num == 22579

    def test_get_build(self, repo: Repo, user: ToolchainUser) -> None:
        customer = user.customers.first()
        customer_id = customer.pk
        repo1 = repo
        repo2 = Repo.create("pothole", customer=customer, name="The Pot Hole")
        repo3 = Repo.create("festivus", customer=customer, name="For the rest of us")
        base_time = utcnow()
        base_time_2 = base_time + datetime.timedelta(minutes=33)
        # This will cause to have "duplicate" run_ids, but that is ok because they will have different partition keys.
        self.seed_dynamodb_data(repo1, user, modifier="for-repo-1", base_time=base_time)
        self.seed_dynamodb_data(repo2, user, modifier="for-repo-2", base_time=base_time_2)
        table = RunInfoTable.for_customer_id(customer_id)
        assert table.get_by_run_id(repo_id=repo1.pk, user_api_id=user.api_id, run_id="jambalaya") is None
        run_id4 = "pants_run_2019_07_19_15_35_18_154_36abaf9ca0894265828d66e1bae1a969"
        run_info = table.get_by_run_id(repo_id=repo1.pk, user_api_id=user.api_id, run_id=run_id4)
        assert run_info.branch == "4"
        assert run_info.buildroot == "for-repo-1"
        assert run_info.server_info.accept_time == base_time
        assert run_info.server_info.environment == "crab/bisque"
        assert run_info.server_info.s3_bucket == "fake-test-buildsense-bucket"
        assert (
            run_info.server_info.s3_key
            == f"no-soup-for-you/buildsense/storage/{repo1.customer_id}/{repo1.id}/{user.api_id}/{run_id4}/final.json"
        )
        assert run_info.server_info.stats_version == "1"
        assert run_info.server_info.request_id == "test-for-repo-1"

        run_info = table.get_by_run_id(repo_id=repo2.pk, user_api_id=user.api_id, run_id=run_id4)
        assert run_info.branch == "4"
        assert run_info.buildroot == "for-repo-2"
        assert run_info.server_info.accept_time == base_time_2
        assert run_info.server_info.environment == "crab/bisque"
        assert run_info.server_info.s3_bucket == "fake-test-buildsense-bucket"
        assert (
            run_info.server_info.s3_key
            == f"no-soup-for-you/buildsense/storage/{repo2.customer_id}/{repo2.id}/{user.api_id}/{run_id4}/final.json"
        )
        assert run_info.server_info.stats_version == "1"
        assert run_info.server_info.request_id == "test-for-repo-2"

        run_info = table.get_by_run_id(repo_id=repo3.pk, user_api_id=user.api_id, run_id=run_id4)
        assert run_info is None
        run_info = table.get_by_run_id(repo_id=repo1.pk, user_api_id="soup", run_id=run_id4)
        assert run_info is None

    def test_bad_gets_builds(self, repo: Repo, user: ToolchainUser) -> None:
        table = RunInfoTable.for_customer_id(repo.customer_id)
        with pytest.raises(ToolchainAssertion, match="run_id can't be empty"):
            table.get_by_run_id(repo_id=repo.pk, user_api_id=user.api_id, run_id="")

        with pytest.raises(ToolchainAssertion, match="Invalid values"):
            table.get_by_run_id(repo_id=repo.pk, user_api_id=None, run_id="jambalaya")

        with pytest.raises(ToolchainAssertion, match="Invalid values"):
            table.get_by_run_id(repo_id="", user_api_id=user.api_id, run_id="jambalaya")

        with pytest.raises(ToolchainAssertion, match="run_id can't be empty"):
            table.get_by_run_id(repo_id="", user_api_id="", run_id="")

        with pytest.raises(ToolchainAssertion, match="Invalid values"):
            table.get_by_run_id(repo_id="", user_api_id="", run_id="jerry!")

    def assert_cursor(self, result, expected_dict):
        last_key_dict = json.loads(base64.b64decode(result.cursor))
        assert last_key_dict == expected_dict
        return last_key_dict

    def test_get_user_builds_with_limit(self, repo: Repo, user: ToolchainUser) -> None:
        bt = datetime.datetime(2019, 5, 13, 13, 50, 30, tzinfo=datetime.timezone.utc)
        delta = datetime.timedelta(hours=7)
        self.seed_dynamodb_data(repo, user, bt, delta)
        table = RunInfoTable.for_customer_id(repo.customer_id)
        result = table.get_user_repo_builds(repo_id=repo.pk, user_api_id=user.api_id)
        assert result.results == tuple()

        result = table.get_user_repo_builds(repo_id=repo.pk, user_api_id=user.api_id, earliest=bt)
        assert len(result.results) == 6
        for run_info in result.results:
            assert run_info.server_info.environment == "crab/bisque"
            assert run_info.server_info.s3_bucket == "fake-test-buildsense-bucket"
            assert (
                run_info.server_info.s3_key
                == f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.id}/{user.api_id}/{run_info.run_id}/final.json"
            )
            assert run_info.server_info.stats_version == "1"
        assert result.count == 6
        assert result.cursor is None

        result = table.get_user_repo_builds(repo_id=repo.pk, user_api_id=user.api_id, earliest=bt, limit=3)
        assert len(result.results) == 3
        assert result.count == 3
        self.assert_cursor(
            result,
            {
                "EnvCustomerRepoUser": f"test:{repo.customer_id}:{repo.id}:{user.api_id}",
                "run_id": "pants_run_2019_07_19_15_35_18_154_36abaf9ca0894265828d66e1bae1a969",
                "run_timestamp": 1557831030,
            },
        )

    def test_get_user_builds_default_time_ranges(self, repo: Repo, user: ToolchainUser) -> None:
        bt = datetime.datetime(2019, 5, 13, 13, 50, 30, tzinfo=datetime.timezone.utc)
        delta = datetime.timedelta(hours=7)
        self.seed_dynamodb_data(repo, user, bt, delta)
        table = RunInfoTable.for_customer_id(repo.customer_id)
        result = table.get_user_repo_builds(repo_id=repo.pk, user_api_id=user.api_id, limit=12)
        assert result.results == tuple()
        assert result.count == 0
        assert result.cursor is None

        result = table.get_user_repo_builds(
            repo_id=repo.pk, user_api_id=user.api_id, earliest=bt + datetime.timedelta(hours=20)
        )
        assert result.count == 3
        items = result.results
        assert len(items) == 3
        assert result.cursor is None
        assert items[0].run_id == "pants_run_2019_07_23_13_27_04_206_2849042e04974d23a1750dc5a290955a"
        assert items[0].branch == "6"
        assert items[0].server_info.environment == "crab/bisque"
        assert items[1].run_id == "pants_run_2019_07_22_15_01_17_10_917f4b304e354a6baaceff913520b926"
        assert items[1].branch == "5"
        assert items[1].server_info.environment == "crab/bisque"
        assert items[0].timestamp > items[1].timestamp  # Ensure descending order

        result = table.get_user_repo_builds(
            repo_id=repo.pk,
            user_api_id=user.api_id,
            earliest=bt + datetime.timedelta(hours=2),
            latest=bt + datetime.timedelta(hours=23),
        )
        assert result.count == 3
        assert len(result.results) == 3
        assert result.cursor is None
        items = result.results
        assert items[0].branch == "4"
        assert items[1].branch == "3"
        assert items[2].branch == "2"
        assert items[0].timestamp > items[1].timestamp > items[2].timestamp  # Ensure descending order

    def test_paginate_user_builds(self, repo: Repo, user: ToolchainUser) -> None:
        bt = datetime.datetime(2019, 5, 13, 13, 50, 30, tzinfo=datetime.timezone.utc)
        delta = datetime.timedelta(hours=7)
        self.seed_dynamodb_data(repo, user, bt, delta)
        table = RunInfoTable.for_customer_id(repo.customer_id)
        result = table.get_user_repo_builds(repo_id=repo.pk, user_api_id=user.api_id, limit=12)
        assert result.results == tuple()
        assert result.count == 0
        assert result.cursor is None

        result = table.get_user_repo_builds(repo_id=repo.pk, user_api_id=user.api_id, earliest=bt, limit=2)
        assert result.count == 2
        items = result.results
        assert len(result.results) == 2
        assert items[0].branch == "6"
        assert items[1].branch == "5"
        last_run_id = "pants_run_2019_07_22_15_01_17_10_917f4b304e354a6baaceff913520b926"
        cursor = result.cursor
        self.assert_cursor(
            result,
            {
                "run_id": last_run_id,
                "run_timestamp": 1557856230,
                "EnvCustomerRepoUser": f"test:{repo.customer_id}:{repo.id}:{user.api_id}",
            },
        )
        result = table.get_user_repo_builds(
            repo_id=repo.pk, user_api_id=user.api_id, earliest=bt, limit=2, cursor=cursor
        )
        assert result.count == 2
        items = result.results
        assert len(result.results) == 2
        assert items[0].branch == "4"
        assert items[1].branch == "3"

        result = table.get_user_repo_builds(
            repo_id=repo.pk, user_api_id=user.api_id, earliest=bt, limit=8, cursor=cursor
        )
        assert result.count == 4
        items = result.results
        assert len(result.results) == 4
        assert items[0].branch == "4"
        assert items[1].branch == "3"
        assert items[2].branch == "2"
        assert items[3].branch == "1"

    def test_paginate_repo_builds(self, repo: Repo, user: ToolchainUser) -> None:
        customer = repo.customer
        user2 = ToolchainUser.create(username="cosmo", email="cosmo@jerrysplace.com")
        customer.add_user(user2)
        bt = datetime.datetime(2019, 5, 13, 13, 50, 30, tzinfo=datetime.timezone.utc)
        delta = datetime.timedelta(hours=7)
        self.seed_dynamodb_data(repo, user, bt, delta, modifier="user-1-elaine")
        bt = datetime.datetime(2019, 5, 13, 13, 20, tzinfo=datetime.timezone.utc)
        delta = datetime.timedelta(hours=3)
        self.seed_dynamodb_data(repo, user2, bt, delta, modifier="user-2-cosmo", run_id_prefix="ovaltine_")

        table = RunInfoTable.for_customer_id(repo.customer_id)
        result = table.get_repo_builds(
            repo_id=repo.pk,
            earliest=datetime.datetime(2019, 5, 13, 12, tzinfo=datetime.timezone.utc),
            latest=datetime.datetime(2019, 5, 18, tzinfo=datetime.timezone.utc),
        )
        assert result.count == 12
        assert result.cursor is None
        items = result.results
        assert len(items) == 12
        assert items[0].run_id == "pants_run_2019_07_23_13_27_04_206_2849042e04974d23a1750dc5a290955a"
        assert items[0].branch == "6"
        assert items[0].buildroot == "user-1-elaine"

        assert items[-1].run_id == "ovaltine_pants_run_2018_06_15_16_04_22_681_b9222bfce9cd421ba1a67ec225a8c6f6"
        assert items[-1].branch == "1"
        assert items[-1].buildroot == "user-2-cosmo"

        result = table.get_repo_builds(
            repo_id=repo.pk,
            earliest=datetime.datetime(2019, 5, 13, 12, tzinfo=datetime.timezone.utc),
            latest=datetime.datetime(2019, 5, 18, tzinfo=datetime.timezone.utc),
            limit=4,
        )
        assert result.count == 4
        cursor = result.cursor
        last_key_dict = self.assert_cursor(
            result,
            {
                "EnvCustomerRepo": f"test:{repo.customer_id}:{repo.id}",
                "run_id": "ovaltine_pants_run_2019_07_23_13_27_04_206_2849042e04974d23a1750dc5a290955a",
                "run_timestamp": "1557807600.0",
                "user_api_id": user2.api_id,
            },
        )
        cursor = base64.b64encode(json.dumps(last_key_dict).encode()).decode()

        items = result.results
        assert len(items) == 4
        assert items[0].run_id == "pants_run_2019_07_23_13_27_04_206_2849042e04974d23a1750dc5a290955a"
        assert items[0].buildroot == "user-1-elaine"
        assert items[-1].run_id == "ovaltine_pants_run_2019_07_23_13_27_04_206_2849042e04974d23a1750dc5a290955a"
        assert items[-1].buildroot == "user-2-cosmo"

        result = table.get_repo_builds(
            repo_id=repo.pk,
            earliest=datetime.datetime(2019, 5, 13, 12, tzinfo=datetime.timezone.utc),
            latest=datetime.datetime(2019, 5, 18, tzinfo=datetime.timezone.utc),
            limit=4,
            cursor=cursor,
        )
        assert result.count == 4
        self.assert_cursor(
            result,
            {
                "EnvCustomerRepo": f"test:{repo.customer_id}:{repo.id}",
                "run_id": "pants_run_2019_07_19_10_22_57_546_1eed7297cc824cef8965b48e8242f061",
                "run_timestamp": "1557780630.0",
                "user_api_id": user.api_id,
            },
        )
        items = result.results
        assert len(items) == 4
        assert items[0].run_id == "pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585"
        assert items[0].buildroot == "user-1-elaine"
        assert items[-1].run_id == "pants_run_2019_07_19_10_22_57_546_1eed7297cc824cef8965b48e8242f061"
        assert items[-1].buildroot == "user-1-elaine"

    def test_iterate_repo_builds(self, table, repo: Repo, user: ToolchainUser) -> None:
        customer = repo.customer
        user2 = ToolchainUser.create(username="cosmo", email="cosmo@jerrysplace.com")
        customer.add_user(user2)
        bt = datetime.datetime(2019, 5, 13, 13, 50, 30, tzinfo=datetime.timezone.utc)
        delta = datetime.timedelta(hours=7)
        self.seed_dynamodb_data(repo, user, bt, delta, modifier="user-1-elaine")
        bt = datetime.datetime(2019, 5, 13, 13, 20, tzinfo=datetime.timezone.utc)
        delta = datetime.timedelta(hours=3)
        self.seed_dynamodb_data(repo, user2, bt, delta, modifier="user-2-cosmo", run_id_prefix="ovaltine_")

        builds_iter = table.iterate_repo_builds(
            repo_id=repo.pk,
            earliest=datetime.datetime(2019, 5, 13, 12, tzinfo=datetime.timezone.utc),
            latest=datetime.datetime(2019, 5, 18, tzinfo=datetime.timezone.utc),
            batch_size=4,
        )
        assert isinstance(builds_iter, GeneratorType)
        items = next(builds_iter)
        assert isinstance(items, tuple)
        assert len(items) == 4
        assert items[0].run_id == "pants_run_2019_07_23_13_27_04_206_2849042e04974d23a1750dc5a290955a"
        assert items[0].buildroot == "user-1-elaine"
        assert items[-1].run_id == "ovaltine_pants_run_2019_07_23_13_27_04_206_2849042e04974d23a1750dc5a290955a"
        assert items[-1].buildroot == "user-2-cosmo"

        items = next(builds_iter)
        assert isinstance(items, tuple)
        assert len(items) == 4
        assert items[0].run_id == "pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585"
        assert items[0].buildroot == "user-1-elaine"
        assert items[-1].run_id == "pants_run_2019_07_19_10_22_57_546_1eed7297cc824cef8965b48e8242f061"
        assert items[-1].buildroot == "user-1-elaine"

    def test_corrupt_cursor_not_b64(self, repo: Repo, user: ToolchainUser) -> None:
        bt = datetime.datetime(2019, 5, 13, 13, 50, 30, tzinfo=datetime.timezone.utc)
        delta = datetime.timedelta(hours=7)
        self.seed_dynamodb_data(repo, user, bt, delta)
        table = RunInfoTable.for_customer_id(repo.customer_id)
        with pytest.raises(InvalidCursorError, match="Failed to decode cursor"):
            table.get_user_repo_builds(
                repo_id=repo.pk, user_api_id=user.api_id, earliest=bt, limit=2, cursor="not-base64-jerry"
            )

    @pytest.mark.parametrize(
        ("cursor", "error_msg"),
        [
            (b"not-json-jerry[]", "Failed to decode cursor"),
            (b"[]", "Invalid json in cursor"),
            (b"{}", "Invalid or missing keys in cursor"),
            (b'{"run_id": "george", "ovaltine": "babu"}', "Invalid or missing keys in cursor"),
            # Extra keys
            (
                b'{"run_id": "vandelay", "user_api_id": "dolores", "run_timestamp": "77", "ovaltine": "costanza"}',
                "Invalid or missing keys in cursor",
            ),
            (
                b'{"run_id": "seinfeld", "user_api_id": "davola", "run_timestamp": "gold", "EnvCustomerRepo": "velvet"}',
                "Invalid run_timestamp: gold",
            ),
            (
                b'{"run_id": "puddy", "user_api_id": "joe", "run_timestamp": 8888, "EnvCustomerRepo": "puffy-shirt"}',
                "Invalid values in cursor",
            ),
            (b'{"run_id": "david", "run_timestamp": 888}', "Invalid or missing keys in cursor"),
        ],
    )
    def test_corrupt_cursor_get_repos(self, repo: Repo, user: ToolchainUser, cursor: bytes, error_msg: str) -> None:
        bt = datetime.datetime(2019, 5, 13, 13, 50, 30, tzinfo=datetime.timezone.utc)
        delta = datetime.timedelta(hours=7)
        self.seed_dynamodb_data(repo, user, bt, delta)
        table = RunInfoTable.for_customer_id(repo.customer_id)
        bad_cursor = base64.b64encode(cursor)
        with pytest.raises(InvalidCursorError, match=error_msg):
            table.get_repo_builds(repo_id=repo.pk, earliest=bt, limit=2, cursor=bad_cursor)

    @pytest.mark.parametrize(
        ("cursor", "error_msg"),
        [
            (b"not-json-jerry[]", "Failed to decode cursor"),
            (b"[]", "Invalid json in cursor"),
            (b"{}", "Invalid or missing keys in cursor"),
            (b'{"run_id": "mulva", "ovaltine": "frogger"}', "Invalid or missing keys in cursor"),
            # Extra keys
            (
                b'{"run_id": "seinfeld", "user_api_id": "festivus", "run_timestamp": "77", "ovaltine": "puddy"}',
                "Invalid or missing keys in cursor",
            ),
            (
                b'{"run_id": "babu", "user_api_id": "newman", "run_timestamp": "gold"}',
                "Invalid or missing keys in cursor",
            ),
            (b'{"run_id": "bob", "user_api_id": "boy", "run_timestamp": 8888}', "Invalid or missing keys in cursor"),
            (b'{"run_id": "bubble", "run_timestamp": 888}', "Invalid or missing keys in cursor"),
        ],
    )
    def test_corrupt_cursor_get_user_repo_buillds(
        self, repo: Repo, user: ToolchainUser, cursor: bytes, error_msg: str
    ) -> None:
        bt = datetime.datetime(2019, 5, 13, 13, 50, 30, tzinfo=datetime.timezone.utc)
        delta = datetime.timedelta(hours=7)
        self.seed_dynamodb_data(repo, user, bt, delta)
        table = RunInfoTable.for_customer_id(repo.customer_id)
        bad_cursor = base64.b64encode(cursor)
        with pytest.raises(InvalidCursorError, match=error_msg):
            table.get_user_repo_builds(
                repo_id=repo.pk, user_api_id=user.api_id, earliest=bt, limit=2, cursor=bad_cursor
            )

    @pytest.mark.parametrize("bad_run_id", [[0, 1, 2], 88, True, None, {}, {"test": {"key": "24"}}])
    def test_corrupt_cursor_invalid_run_id(self, repo: Repo, user: ToolchainUser, bad_run_id) -> None:
        bt = datetime.datetime(2019, 5, 13, 13, 50, 30, tzinfo=datetime.timezone.utc)
        delta = datetime.timedelta(hours=7)
        self.seed_dynamodb_data(repo, user, bt, delta)
        table = RunInfoTable.for_customer_id(repo.customer_id)
        bad_cursor = base64.b64encode(
            json.dumps({"run_id": bad_run_id, "run_timestamp": 1557807600.0, "EnvCustomerRepoUser": "jerry"}).encode()
        ).decode()
        with pytest.raises(InvalidCursorError, match="Invalid values in cursor"):
            table.get_user_repo_builds(
                repo_id=repo.pk, user_api_id=user.api_id, earliest=bt, limit=2, cursor=bad_cursor
            )

    def test_batch_get_items_error(self, repo: Repo) -> None:
        table = RunInfoTable.for_customer_id(repo.customer_id)
        with pytest.raises(ToolchainAssertion, match="Empty RunKeys"):
            table.get_by_run_ids([])

    def test_batch_get_items(self, repo: Repo, user: ToolchainUser) -> None:
        customer = repo.customer
        user2 = ToolchainUser.create(username="cosmo", email="cosmo@jerrysplace.com")

        customer.add_user(user2)
        bt = datetime.datetime(2019, 5, 13, 13, 50, 30, tzinfo=datetime.timezone.utc)
        delta = datetime.timedelta(hours=7)
        self.seed_dynamodb_data(repo, user, bt, delta, modifier="user-1-elaine")
        bt = datetime.datetime(2019, 5, 13, 13, 20, tzinfo=datetime.timezone.utc)
        delta = datetime.timedelta(hours=3)
        self.seed_dynamodb_data(repo, user2, bt, delta, modifier="user-2-cosmo", run_id_prefix="ovaltine_")

        keys = [
            RunKey(
                user_api_id=user.api_id,
                repo_id=repo.pk,
                run_id="pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585",
            ),
            RunKey(
                user_api_id=user.api_id,
                repo_id=repo.pk,
                run_id="pants_run_2019_07_19_15_35_18_154_36abaf9ca0894265828d66e1bae1a969",
            ),
            RunKey(
                user_api_id=user.api_id,
                repo_id=repo.pk,
                run_id="pants_run_2019_07_23_13_27_04_206_2849042e04974d23a1750dc5a290955a",
            ),
            RunKey(
                user_api_id=user2.api_id,
                repo_id=repo.pk,
                run_id="ovaltine_pants_run_2019_07_19_15_35_18_154_36abaf9ca0894265828d66e1bae1a969",
            ),
            RunKey(
                user_api_id=user2.api_id,
                repo_id=repo.pk,
                run_id="ovaltine_pants_run_2018_06_15_16_04_22_681_b9222bfce9cd421ba1a67ec225a8c6f6",
            ),
        ]
        table = RunInfoTable.for_customer_id(repo.customer_id)
        ordered_run_ids = [result.run_id for result in table.get_by_run_ids(keys)]
        assert ordered_run_ids == [
            "pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585",
            "pants_run_2019_07_19_15_35_18_154_36abaf9ca0894265828d66e1bae1a969",
            "pants_run_2019_07_23_13_27_04_206_2849042e04974d23a1750dc5a290955a",
            "ovaltine_pants_run_2019_07_19_15_35_18_154_36abaf9ca0894265828d66e1bae1a969",
            "ovaltine_pants_run_2018_06_15_16_04_22_681_b9222bfce9cd421ba1a67ec225a8c6f6",
        ]

        keys = [
            RunKey(
                user_api_id=user.api_id,
                repo_id=repo.pk,
                run_id="pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585",
            ),
            RunKey(
                user_api_id=user.api_id,
                repo_id=repo.pk,
                run_id="pants_run_2019_07_19_15_35_18_154_36abaf9ca0894265828d66e1bae1a969",
            ),
            RunKey(
                user_api_id="some_id",
                repo_id=repo.pk,
                run_id="pants_run_2019_07_23_13_27_04_206_2849042e04974d23a1750dc5a290955a",
            ),
            RunKey(
                user_api_id=user2.api_id,
                repo_id=repo.pk,
                run_id="ovaltine_pants_run_2019_07_19_15_35_18_154_36abaf9ca0894265828d66e1bae1a969",
            ),
            RunKey(
                user_api_id=user2.api_id,
                repo_id=repo.pk,
                run_id="ovaltine_pants_run_2018_06_15_16_04_22_681_b9222bfce9cd421ba1a67ec225a8c6f6",
            ),
        ]
        ordered_run_ids = [result.run_id for result in table.get_by_run_ids(keys)]
        assert ordered_run_ids == [
            "pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585",
            "pants_run_2019_07_19_15_35_18_154_36abaf9ca0894265828d66e1bae1a969",
            "ovaltine_pants_run_2019_07_19_15_35_18_154_36abaf9ca0894265828d66e1bae1a969",
            "ovaltine_pants_run_2018_06_15_16_04_22_681_b9222bfce9cd421ba1a67ec225a8c6f6",
        ]

        keys = [
            RunKey(
                user_api_id=user.api_id,
                repo_id=repo.pk,
                run_id="pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585",
            ),
            RunKey(
                user_api_id=user.api_id,
                repo_id="blaabla",
                run_id="pants_run_2019_07_19_15_35_18_154_36abaf9ca0894265828d66e1bae1a969",
            ),
            RunKey(
                user_api_id=user.api_id,
                repo_id=repo.pk,
                run_id="pants_run_2019_07_23_13_27_04_206_2849042e04974d23a1750dc5a290955a",
            ),
            RunKey(
                user_api_id=user2.api_id,
                repo_id=repo.pk,
                run_id="ovaltine_pants_run_2019_07_19_15_35_18_154_36abaf9ca0894265828d66e1bae1a969",
            ),
            RunKey(
                user_api_id=user2.api_id,
                repo_id=repo.pk,
                run_id="ovaltine_pants_run_2018_06_15_16_04_22_681_b9222bfce9cd421ba1a67ec225a8c6f6",
            ),
        ]
        ordered_run_ids = [result.run_id for result in table.get_by_run_ids(keys)]
        assert ordered_run_ids == [
            "pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585",
            "pants_run_2019_07_23_13_27_04_206_2849042e04974d23a1750dc5a290955a",
            "ovaltine_pants_run_2019_07_19_15_35_18_154_36abaf9ca0894265828d66e1bae1a969",
            "ovaltine_pants_run_2018_06_15_16_04_22_681_b9222bfce9cd421ba1a67ec225a8c6f6",
        ]

        ordered_run_ids = [result.run_id for result in table.get_by_run_ids(keys, repo_id=repo.pk)]
        assert ordered_run_ids == [
            "pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585",
            "pants_run_2019_07_19_15_35_18_154_36abaf9ca0894265828d66e1bae1a969",
            "pants_run_2019_07_23_13_27_04_206_2849042e04974d23a1750dc5a290955a",
            "ovaltine_pants_run_2019_07_19_15_35_18_154_36abaf9ca0894265828d66e1bae1a969",
            "ovaltine_pants_run_2018_06_15_16_04_22_681_b9222bfce9cd421ba1a67ec225a8c6f6",
        ]

    def test_batch_get_items_multiple_repos(self, repo: Repo, user: ToolchainUser) -> None:
        customer = repo.customer
        repo2 = Repo.create("soup", customer, "No Soup for you")
        bt = datetime.datetime(2019, 5, 13, 13, 50, 30, tzinfo=datetime.timezone.utc)
        delta = datetime.timedelta(hours=7)
        self.seed_dynamodb_data(repo, user, bt, delta, modifier="user-1-elaine")
        bt = datetime.datetime(2019, 5, 13, 13, 20, tzinfo=datetime.timezone.utc)
        delta = datetime.timedelta(hours=3)
        self.seed_dynamodb_data(repo2, user, bt, delta, modifier="user-2-cosmo", run_id_prefix="ovaltine_")
        keys = [
            RunKey(
                user_api_id=user.api_id,
                repo_id=repo.pk,
                run_id="pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585",
            ),
            RunKey(
                user_api_id=user.api_id,
                repo_id=repo.pk,
                run_id="pants_run_2019_07_19_15_35_18_154_36abaf9ca0894265828d66e1bae1a969",
            ),
            RunKey(
                user_api_id=user.api_id,
                repo_id=repo.pk,
                run_id="pants_run_2019_07_23_13_27_04_206_2849042e04974d23a1750dc5a290955a",
            ),
            RunKey(
                user_api_id=user.api_id,
                repo_id=repo.pk,
                run_id="ovaltine_pants_run_2019_07_19_15_35_18_154_36abaf9ca0894265828d66e1bae1a969",
            ),
            RunKey(
                user_api_id=user.api_id,
                repo_id=repo.pk,
                run_id="ovaltine_pants_run_2018_06_15_16_04_22_681_b9222bfce9cd421ba1a67ec225a8c6f6",
            ),
        ]
        table = RunInfoTable.for_customer_id(customer.pk)
        run_infos = table.get_by_run_ids(keys)
        assert len(run_infos) == 3  # Wrong repo ids on last 2

        keys = [
            RunKey(
                user_api_id=user.api_id,
                repo_id=repo.pk,
                run_id="pants_run_2019_07_19_12_11_26_410_3daadd52871f457bad18712f2579f585",
            ),
            RunKey(
                user_api_id=user.api_id,
                repo_id=repo.pk,
                run_id="pants_run_2019_07_19_15_35_18_154_36abaf9ca0894265828d66e1bae1a969",
            ),
            RunKey(
                user_api_id=user.api_id,
                repo_id=repo.pk,
                run_id="pants_run_2019_07_23_13_27_04_206_2849042e04974d23a1750dc5a290955a",
            ),
            RunKey(
                user_api_id=user.api_id,
                repo_id=repo2.pk,
                run_id="ovaltine_pants_run_2019_07_19_15_35_18_154_36abaf9ca0894265828d66e1bae1a969",
            ),
            RunKey(
                user_api_id=user.api_id,
                repo_id=repo2.pk,
                run_id="ovaltine_pants_run_2018_06_15_16_04_22_681_b9222bfce9cd421ba1a67ec225a8c6f6",
            ),
        ]
        run_infos = table.get_by_run_ids(keys)
        assert len(run_infos) == 5

    def _prep_data_with_additinal_field(self, repo: Repo, user: ToolchainUser, fixture_name: str) -> RunInfo:
        table = RunInfoTable.for_customer_id(repo.customer_id)
        run_info = load_run_info(fixture_name, repo=repo, user=user)
        partition_key, partition_value = table._get_user_partition_info(repo.id, user.api_id)
        gsi_key, gsi_value = table._get_repo_partition_info(repo.id)
        record = run_info.to_json_dict()
        record.update(
            {
                partition_key: partition_value,
                gsi_key: gsi_value,
                "Environment": table._env,
                "run_timestamp": int(record.pop("timestamp")),
            }
        )
        record["costanza"] = "He stopped short?"
        table._get_table().put_item(record=record, expression="", expression_values={})
        return run_info

    def test_load_run_info_with_new_field(self, repo: Repo, user: ToolchainUser) -> None:
        run_info = self._prep_data_with_additinal_field(repo, user, "buildkite_github_branch_lint_run")
        table = RunInfoTable.for_customer_id(repo.customer_id)
        table.get_by_run_id(repo_id=repo.pk, user_api_id=user.api_id, run_id=run_info.run_id)


class TestRunInfoTableWriteData(BaseRunInfoTableTests):
    def test_save_run(self, table: RunInfoTable, repo: Repo, user: ToolchainUser) -> None:
        data = load_fixture("sample_9_end")
        server_info = ServerInfo(
            request_id="test-save-run",
            accept_time=utcnow(),
            stats_version="2",
            environment="low-flow",
            s3_bucket="chicken",
            s3_key="little-jerry-seinfeld",
        )
        run_info = parse_run_info(fixture_data=data, repo=repo, user=user, server_info=server_info)
        assert table.save_run(run_info) is True
        self._assert_run_info(table, repo, user, data["run_info"]["id"], server_info)

    def test_save_run_with_ci_info(self, table: RunInfoTable, repo: Repo, user: ToolchainUser) -> None:
        data = load_fixture("ci_build_branch_final_1")
        run_id = data["run_info"]["id"]
        server_info = ServerInfo(
            request_id="test-save-run",
            accept_time=utcnow(),
            stats_version="2",
            environment="low-flow",
            s3_bucket="chicken",
            s3_key="little-jerry-seinfeld",
        )
        run_info = parse_run_info(fixture_data=data, repo=repo, user=user, server_info=server_info)
        assert table.save_run(run_info) is True
        loaded_run_info = table.get_by_run_id(repo_id=repo.pk, user_api_id=user.api_id, run_id=run_id)
        assert loaded_run_info is not None
        assert loaded_run_info.server_info == server_info
        # NB: This Pants version is hardcoded.
        assert loaded_run_info.version == "2.0.0.dev6"
        assert loaded_run_info.outcome == "SUCCESS"
        assert loaded_run_info.run_id == "pants_run_2020_08_14_17_17_32_751_5263973c8e154a7fb3d8f98232dd24f2"
        assert loaded_run_info.ci_info is not None
        assert loaded_run_info.ci_info.run_type == CIDetails.Type.BRANCH
        assert loaded_run_info.ci_info.pull_request is None
        assert loaded_run_info.ci_info.job_name == "build"
        assert loaded_run_info.ci_info.username == "Eric-Arellano"
        assert loaded_run_info.ci_info.build_url == "https://circleci.com/gh/toolchainlabs/toolchain/22688"
        assert loaded_run_info.ci_info.build_num == 22688

    def test_save_run_existing(self, table: RunInfoTable, repo: Repo, user: ToolchainUser) -> None:
        data = load_fixture("sample_9_end")
        run_id = data["run_info"]["id"]
        server_info = ServerInfo(
            request_id="test-save-run",
            accept_time=utcnow(),
            stats_version="2",
            environment="low-flow",
            s3_bucket="chicken",
            s3_key="little-jerry-seinfeld",
        )
        run_info = parse_run_info(fixture_data=data, repo=repo, user=user, server_info=server_info)
        assert table.save_run(run_info) is True
        server_info_2 = ServerInfo(
            request_id="test-letterman",
            accept_time=utcnow(),
            stats_version="2",
            environment="low-flow",
            s3_bucket="the-buttler",
            s3_key="little-jerry-seinfeld",
        )
        data = load_fixture("sample_9_end")
        data.update(version="marla", outcome="ABORTED")
        run_info = parse_run_info(fixture_data=data, repo=repo, user=user, server_info=server_info_2)
        assert table.save_run(run_info) is False
        self._assert_run_info(table, repo, user, run_id, server_info)

    def test_save_run_with_indicators(self, table: RunInfoTable, repo: Repo, user: ToolchainUser) -> None:
        data = load_fixture("run_typecheck_with_metrics.legacy_counters")
        server_info = ServerInfo(
            request_id="test-save-run",
            accept_time=datetime.datetime(2021, 8, 10, tzinfo=datetime.timezone.utc),
            stats_version="2",
            environment="low-flow",
            s3_bucket="chicken",
            s3_key="little-jerry-seinfeld",
        )
        run_info = parse_run_info(fixture_data=data, repo=repo, user=user, server_info=server_info)
        run_info.indicators = {
            "used_cpu_time": 160429,
            "saved_cpu_time": 373895,
            "hits": 1103,
            "total": 1178,
            "hit_fraction": 0.9363327674023769,
        }
        assert table.save_run(run_info) is True
        loaded_run_info = table.get_by_run_id(
            repo_id=repo.pk,
            user_api_id=user.api_id,
            run_id="pants_run_2020_11_02_20_24_01_120_31f8258d0ab44329bd00d47c3a79ec88",
        )
        assert loaded_run_info is not None
        assert loaded_run_info.server_info == server_info
        assert loaded_run_info.version == "2.1.0.dev0"
        assert loaded_run_info.outcome == "SUCCESS"
        assert loaded_run_info.run_id == "pants_run_2020_11_02_20_24_01_120_31f8258d0ab44329bd00d47c3a79ec88"
        assert loaded_run_info.indicators == {
            "used_cpu_time": 160429,
            "saved_cpu_time": 373895,
            "hits": 1103,
            "total": 1178,
            "hit_fraction": 0.936333,
        }

    def test_update_or_insert_run(self, table: RunInfoTable, repo: Repo, user: ToolchainUser) -> None:
        data_1 = load_fixture("sample_9_start")
        run_id = data_1["run_info"]["id"]
        server_info_1 = ServerInfo(
            request_id="reneging",
            accept_time=utcnow(),
            stats_version="2",
            environment="low-flow",
            s3_bucket="chicken",
            s3_key="pirate",
        )
        run_info_1 = parse_run_info(fixture_data=data_1, repo=repo, user=user, server_info=server_info_1)
        assert table.save_run(run_info_1) is True
        loaded_run_info = table.get_by_run_id(repo_id=repo.pk, user_api_id=user.api_id, run_id=run_id)
        assert loaded_run_info is not None
        assert loaded_run_info.server_info == server_info_1
        assert loaded_run_info.outcome == "NOT_AVAILABLE"

        data_2 = load_fixture("sample_9_end")
        server_info_2 = ServerInfo(
            request_id="palisades-interstate-parkway",
            accept_time=utcnow(),
            stats_version="2",
            environment="karma-kramer",
            s3_bucket="party",
            s3_key="crazy-joe-davola",
        )
        run_info_2 = parse_run_info(fixture_data=data_2, repo=repo, user=user, server_info=server_info_2)
        assert table.update_or_insert_run(run_info_2) is True
        self._assert_run_info(table, repo, user, run_id, server_info_2)

    def _save_run(
        self, fixture: str, accept_time: datetime.datetime, table: RunInfoTable, repo: Repo, user: ToolchainUser
    ) -> str:
        data_1 = load_fixture(fixture)
        run_id = data_1["run_info"]["id"]
        server_info_1 = ServerInfo(
            request_id="reneging",
            accept_time=accept_time,
            stats_version="2",
            environment="low-flow",
            s3_bucket="chicken",
            s3_key="pirate",
        )
        run_info_1 = parse_run_info(fixture_data=data_1, repo=repo, user=user, server_info=server_info_1)
        assert table.save_run(run_info_1) is True
        return run_id

    def test_update_work_units(self, table: RunInfoTable, repo: Repo, user: ToolchainUser) -> None:
        start_time = utcnow() - datetime.timedelta(minutes=30)
        run_id = self._save_run("sample_9_start", start_time, table, repo, user)
        loaded_run_info = table.get_by_run_id(repo_id=repo.pk, user_api_id=user.api_id, run_id=run_id)
        assert loaded_run_info is not None
        assert loaded_run_info.server_info.accept_time == start_time
        update_time = utcnow() - datetime.timedelta(minutes=3)
        updated = table.update_workunits(
            repo_id=repo.pk, user_api_id=user.api_id, run_id=run_id, last_update=update_time, workunits=[]
        )
        assert updated is True
        assert get_table_items_count() == 1
        loaded_run_info = table.get_by_run_id(repo_id=repo.pk, user_api_id=user.api_id, run_id=run_id)
        assert loaded_run_info is not None
        assert loaded_run_info.server_info.accept_time == update_time

    def test_update_work_units_dont_update_finished_build(
        self, table: RunInfoTable, repo: Repo, user: ToolchainUser
    ) -> None:
        accept_time = utcnow() - datetime.timedelta(minutes=13)
        run_id = self._save_run("sample_9_end", accept_time, table, repo, user)
        update_time = utcnow() - datetime.timedelta(minutes=3)
        updated = table.update_workunits(
            repo_id=repo.pk, user_api_id=user.api_id, run_id=run_id, last_update=update_time, workunits=[]
        )
        assert updated is False
        loaded_run_info = table.get_by_run_id(repo_id=repo.pk, user_api_id=user.api_id, run_id=run_id)
        assert loaded_run_info is not None
        assert loaded_run_info.server_info.accept_time == accept_time

    def test_update_work_units_dont_create_non_existing(
        self, table: RunInfoTable, repo: Repo, user: ToolchainUser
    ) -> None:
        update_time = utcnow() - datetime.timedelta(minutes=3)
        updated = table.update_workunits(
            repo_id=repo.pk, user_api_id=user.api_id, run_id="some_run_id", last_update=update_time, workunits=[]
        )
        assert updated is False
        assert not get_table_items()

    def _assert_run_info(
        self, table: RunInfoTable, repo: Repo, user: ToolchainUser, run_id: str, server_info: ServerInfo
    ) -> RunInfo:
        loaded_run_info = table.get_by_run_id(repo_id=repo.pk, user_api_id=user.api_id, run_id=run_id)
        assert loaded_run_info is not None
        assert loaded_run_info.server_info == server_info
        # NB: This Pants version is hardcoded.
        assert loaded_run_info.version == "1.25.0.dev1"
        assert loaded_run_info.outcome == "SUCCESS"
        assert loaded_run_info.run_id == "pants_run_2020_01_23_11_41_55_931_68189fba67f94d7ebd9b119f4966124c"
        return loaded_run_info

    def test_delete_build(self, table: RunInfoTable, repo: Repo, user: ToolchainUser) -> None:
        run_id = self._save_run("sample_9_end", utcnow(), table, repo, user)
        assert table.get_by_run_id(repo_id=repo.pk, user_api_id=user.api_id, run_id=run_id) is not None
        table.delete_build(repo_id=repo.pk, user_api_id=user.api_id, run_id=run_id)
        assert table.get_by_run_id(repo_id=repo.pk, user_api_id=user.api_id, run_id=run_id) is None

    def test_delete_builds_invalid_call(self, table: RunInfoTable) -> None:
        with pytest.raises(ToolchainAssertion, match="Empty RunKeys"):
            table.delete_builds(run_keys=[])

    def test_delete_builds(self, table: RunInfoTable, repo: Repo, user: ToolchainUser) -> None:
        bt = datetime.datetime(2019, 5, 13, 13, 50, 30, tzinfo=datetime.timezone.utc)
        run_ids = self.seed_dynamodb_data(repo, user, bt, datetime.timedelta(minutes=3), modifier="user-elaine")
        assert get_table_items_count() == 6
        keys = [RunKey(user_api_id=user.api_id, repo_id=repo.pk, run_id=run_id) for run_id in run_ids]
        table.delete_builds(run_keys=keys[:3])
        assert get_table_items_count() == 3
