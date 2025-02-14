# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

import pytest

from toolchain.base.datetime_tools import utcnow
from toolchain.buildsense.ingestion.models import (
    ConfigureRepoMetricsBucket,
    IndexPantsMetrics,
    ProcessBuildDataRetention,
    ProcessPantsRun,
    ProcessQueuedBuilds,
    RunState,
)
from toolchain.buildsense.records.run_info import RunInfo, ServerInfo
from toolchain.buildsense.test_utils.data_loader import parse_run_info
from toolchain.buildsense.test_utils.fixtures_loader import load_fixture
from toolchain.django.site.models import Customer, Repo, ToolchainUser
from toolchain.workflow.models import WorkUnit
from toolchain.workflow.work_dispatcher_test import mark_work_unit_success


def _get_fixture(fixture: str) -> tuple[RunInfo, ToolchainUser, Repo]:
    user = ToolchainUser.create(username="kramer", email="kramer@jerrysplace.com")
    customer = Customer.create(slug="whatley", name="acme")
    customer.add_user(user)
    repo = Repo.create("ovaltine", customer=customer, name="acmebot")
    server_info = ServerInfo(
        request_id="test",
        accept_time=utcnow(),
        stats_version="1",
        environment="jambalaya",
        s3_bucket="puffy",
        s3_key="pirate",
    )
    build_data = load_fixture(fixture)
    run_info = parse_run_info(fixture_data=build_data, repo=repo, user=user, server_info=server_info)
    return run_info, user, repo


@pytest.mark.django_db()
class TestProcessPantsRun:
    def test_create(self) -> None:
        run_info, user, repo = _get_fixture("sample2")
        assert ProcessPantsRun.objects.count() == 0
        ppr = ProcessPantsRun.create(run_info, repo=repo)
        assert ppr.run_id == "pants_run_2019_07_19_10_22_57_546_1eed7297cc824cef8965b48e8242f061"
        assert ppr.repo_id == repo.pk
        assert ppr.user_api_id == user.api_id
        assert (
            ppr.description
            == f"repo=whatley/ovaltine run_id=pants_run_2019_07_19_10_22_57_546_1eed7297cc824cef8965b48e8242f061 repo_id={repo.pk} user_api_id={user.api_id}"
        )

        assert ProcessPantsRun.objects.count() == 1
        loaded_ppr = ProcessPantsRun.objects.first()
        assert loaded_ppr == ppr
        assert loaded_ppr.run_id == "pants_run_2019_07_19_10_22_57_546_1eed7297cc824cef8965b48e8242f061"
        assert loaded_ppr.repo_id == repo.pk
        assert loaded_ppr.user_api_id == user.api_id
        assert loaded_ppr.state == RunState.ACTIVE
        assert loaded_ppr.is_deleted is False
        assert (
            loaded_ppr.description
            == f"repo=whatley/ovaltine run_id=pants_run_2019_07_19_10_22_57_546_1eed7297cc824cef8965b48e8242f061 repo_id={repo.pk} user_api_id={user.api_id}"
        )

    def test_mark_as_deleted(self):
        run_info, _, repo = _get_fixture("sample2")
        ppr = ProcessPantsRun.create(run_info, repo=repo)
        assert ppr.mark_as_deleted() is True
        assert ppr.mark_as_deleted() is False
        assert ppr.is_deleted is True
        assert ppr.state == RunState.DELETED
        assert ProcessPantsRun.objects.count() == 1
        loaded_ppr = ProcessPantsRun.objects.first()
        assert loaded_ppr.is_deleted is True
        assert loaded_ppr.state == RunState.DELETED
        assert loaded_ppr.mark_as_deleted() is False


@pytest.mark.django_db()
class TestProcessQueuedBuilds:
    def test_create(self):
        customer = Customer.create(slug="whatley", name="acme")
        repo = Repo.create("ovaltine", customer=customer, name="acmebot")
        pqb = ProcessQueuedBuilds.create(repo=repo, bucket="bosco", key="del/boca/vista", num_of_builds=12)
        assert pqb.repo_id == repo.id
        assert pqb.bucket == "bosco"
        assert pqb.key == "del/boca/vista"
        assert pqb.num_of_builds == 12


@pytest.mark.django_db()
class TestIndexPantsMetrics:
    def test_create(self) -> None:
        run_info, user, repo = _get_fixture("build_end_workunits_v3")
        assert IndexPantsMetrics.objects.count() == 0
        ipm = IndexPantsMetrics.create_or_rerun(run_info, repo=repo)
        assert IndexPantsMetrics.objects.count() == 1

        assert ipm.run_id == "pants_run_2020_05_07_09_54_18_542_e2204cccbe534499befbc04c8da2f886"
        assert ipm.repo_id == repo.pk
        assert ipm.user_api_id == user.api_id
        assert ipm.state == RunState.ACTIVE
        assert ipm.is_deleted is False

    def test_rerun(self) -> None:
        run_info, user, repo = _get_fixture("build_end_workunits_v3")
        assert IndexPantsMetrics.objects.count() == 0
        ipm = IndexPantsMetrics.create_or_rerun(run_info, repo=repo)
        assert IndexPantsMetrics.objects.count() == 1
        wu = mark_work_unit_success(ipm)

        ipm = IndexPantsMetrics.create_or_rerun(run_info, repo=repo)
        assert IndexPantsMetrics.objects.count() == 1
        assert ipm.work_unit_id == wu.id
        assert ipm.work_unit.state == "REA"
        assert ipm.run_id == "pants_run_2020_05_07_09_54_18_542_e2204cccbe534499befbc04c8da2f886"
        assert ipm.repo_id == repo.pk
        assert ipm.user_api_id == user.api_id

    def test_mark_as_deleted(self):
        run_info, _, repo = _get_fixture("build_end_workunits_v3")
        ipm = IndexPantsMetrics.create_or_rerun(run_info, repo=repo)
        assert ipm.mark_as_deleted() is True
        assert ipm.mark_as_deleted() is False
        assert ipm.is_deleted is True
        assert ipm.state == RunState.DELETED
        assert IndexPantsMetrics.objects.count() == 1
        loaded_ipm = IndexPantsMetrics.objects.first()
        assert loaded_ipm.is_deleted is True
        assert loaded_ipm.state == RunState.DELETED
        assert loaded_ipm.mark_as_deleted() is False


@pytest.mark.django_db()
class TestProcessBuildDataRetention:
    @pytest.fixture()
    def repo(self) -> Repo:
        customer = Customer.create(slug="whatley", name="tim w.")
        return Repo.create("ovaltine", customer=customer, name="newman")

    def test_create_or_update_for_repo_default(self, repo: Repo) -> None:
        bdr = ProcessBuildDataRetention.create_or_update_for_repo(repo=repo)
        assert bdr.period_minutes is None
        assert bdr.retention_days == 9125
        assert bdr.repo_id == repo.id
        assert bdr.dry_run is True
        assert "retention 9,125 days. run once. dry_run=True" in bdr.description

    def test_create_or_update_for_repo(self, repo: Repo) -> None:
        bdr = ProcessBuildDataRetention.create_or_update_for_repo(
            repo=repo, retention_days=360, period_minutes=240, dry_run=False
        )
        assert bdr.period_minutes == 240
        assert bdr.retention_days == 360
        assert bdr.repo_id == repo.id
        assert "retention 360 days. run every 240 minutes. dry_run=False" in bdr.description
        assert bdr.dry_run is False

    def test_update(self, repo: Repo) -> None:
        ProcessBuildDataRetention.create_or_update_for_repo(repo=repo)
        bdr = ProcessBuildDataRetention.create_or_update_for_repo(
            repo=repo, retention_days=360, period_minutes=240, dry_run=False
        )
        assert bdr.period_minutes == 240
        assert bdr.retention_days == 360
        assert bdr.repo_id == repo.id
        assert bdr.dry_run is False
        assert "retention 360 days. run every 240 minutes. dry_run=False" in bdr.description
        assert ProcessBuildDataRetention.objects.count() == 1

    def test_create_with_no_retention(self, repo: Repo) -> None:
        bdr = ProcessBuildDataRetention.create_or_update_for_repo(
            repo=repo, retention_days=0, period_minutes=240, dry_run=False
        )
        assert bdr.period_minutes == 240
        assert bdr.retention_days == 0
        assert bdr.repo_id == repo.id
        assert bdr.dry_run is False
        assert "retention 0 days. run every 240 minutes. dry_run=False" in bdr.description


@pytest.mark.django_db()
class TestConfigureRepoMetricsBucket:
    @pytest.fixture()
    def repo(self) -> Repo:
        customer = Customer.create(slug="whatley", name="tim w.")
        return Repo.create("ovaltine", customer=customer, name="newman")

    def test_create(self, repo: Repo) -> None:
        crmb = ConfigureRepoMetricsBucket.run_for_repo(repo_id=repo.id)
        assert crmb.repo_id == repo.id
        assert crmb.work_unit.state == WorkUnit.READY

    def test_re_run(self, repo: Repo) -> None:
        mark_work_unit_success(ConfigureRepoMetricsBucket.run_for_repo(repo_id=repo.id))
        crmb = ConfigureRepoMetricsBucket.run_for_repo(repo_id=repo.id)
        assert crmb.repo_id == repo.id
        assert crmb.work_unit.state == WorkUnit.READY

    def test_dont_re_run_pending(self, repo: Repo) -> None:
        wu = ConfigureRepoMetricsBucket.run_for_repo(repo_id=repo.id).work_unit
        now = utcnow()
        wu.take_lease(until=now + datetime.timedelta(minutes=20), last_attempt=now, node="happy-festivus")
        crmb = ConfigureRepoMetricsBucket.run_for_repo(repo_id=repo.id)
        assert crmb.repo_id == repo.id
        assert crmb.work_unit.state == WorkUnit.LEASED

    def test_dont_re_run_failed(self, repo: Repo) -> None:
        wu = ConfigureRepoMetricsBucket.run_for_repo(repo_id=repo.id).work_unit
        now = utcnow()
        wu.take_lease(until=now + datetime.timedelta(minutes=20), last_attempt=now, node="happy-festivus")
        wu.permanent_error_occurred()
        crmb = ConfigureRepoMetricsBucket.run_for_repo(repo_id=repo.id)
        assert crmb.repo_id == repo.id
        assert crmb.work_unit.state == WorkUnit.INFEASIBLE
