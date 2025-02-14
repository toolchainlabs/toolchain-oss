# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

import pytest
from freezegun import freeze_time

from toolchain.base.datetime_tools import utcnow
from toolchain.dependency.models import CleanOldSolutions, PeriodicallyCleanOldSolutions, ResolverSolution
from toolchain.dependency.workers.periodic_solutions_remover import OldSolutionRemover, PeriodicSolutionRemover


def _generate_solutions(base_time, count: int) -> list[str]:
    parameters = {"py": "3.8", "abi": "abi3", "platform": "linux"}
    solution_dict = {
        "releases": [{"project_name": "aaa", "version": "1.0.0", "sha256": "close-talker"}],
        "dependencies": [],
    }
    leveldb_version = 19
    solution_ids = []
    for _ in range(count):
        with freeze_time(base_time):
            sr = ResolverSolution.get_or_create(
                dependencies=["festivus=9.1.3", f"bagels==10.88.{base_time.day}"],
                parameters=parameters,
                leveldb_version=leveldb_version,
            )
            ResolverSolution.store_solution(sr.solution_id, solution_dict)
        solution_ids.append(sr.solution_id)
        base_time -= datetime.timedelta(days=1)
        leveldb_version += 2
    return solution_ids


@pytest.mark.django_db()
class TestOldSolutionRemover:
    def test_do_work(self):
        base_time = utcnow() - datetime.timedelta(days=20)
        payload = CleanOldSolutions.create(base_time - datetime.timedelta(days=19, hours=4))
        _generate_solutions(base_time, 30)
        assert ResolverSolution.objects.count() == 30
        remover = OldSolutionRemover()
        assert remover.do_work(payload) is True
        assert ResolverSolution.objects.count() == 20


@pytest.mark.django_db()
class TestPeriodicSolutionRemover:
    def test_do_work_one_time_initial(self):
        payload = PeriodicallyCleanOldSolutions.objects.create(period_minutes=None, threshold_days=10)
        assert PeriodicSolutionRemover().do_work(payload) is False

    def test_do_work_one_time(self):
        payload = PeriodicallyCleanOldSolutions.objects.create(period_minutes=None, threshold_days=10)
        remover = PeriodicSolutionRemover()
        assert remover.do_work(payload) is False
        assert remover.on_reschedule(payload) is None
        wu = payload.work_unit
        wu.refresh_from_db()
        assert wu.num_unsatisfied_requirements == 1

        # Next run
        payload = PeriodicallyCleanOldSolutions.objects.first()
        assert PeriodicSolutionRemover().do_work(payload) is True

    def test_do_work_periodic_initial(self):
        payload = PeriodicallyCleanOldSolutions.objects.create(period_minutes=90, threshold_days=10)
        assert PeriodicSolutionRemover().do_work(payload) is False

    def test_do_work_periodic(self):
        payload = PeriodicallyCleanOldSolutions.objects.create(period_minutes=10, threshold_days=10)
        remover = PeriodicSolutionRemover()
        assert remover.do_work(payload) is False
        next_time = remover.on_reschedule(payload)
        assert next_time.timestamp() == pytest.approx((utcnow() + datetime.timedelta(minutes=10)).timestamp())
        wu = payload.work_unit
        wu.refresh_from_db()
        assert wu.num_unsatisfied_requirements == 1

        # Next run
        payload = PeriodicallyCleanOldSolutions.objects.first()
        assert PeriodicSolutionRemover().do_work(payload) is False

    def test_on_reschedule_periodic(self):
        payload = PeriodicallyCleanOldSolutions.objects.create(period_minutes=90, threshold_days=10)
        assert CleanOldSolutions.objects.count() == 0
        next_time = PeriodicSolutionRemover().on_reschedule(payload)
        assert next_time.timestamp() == pytest.approx((utcnow() + datetime.timedelta(minutes=90)).timestamp())
        assert CleanOldSolutions.objects.count() == 1
        # datetime.datetime.min since we didn't run do_work()
        assert CleanOldSolutions.objects.first().threshold == datetime.datetime.min.replace(
            tzinfo=datetime.timezone.utc
        )
        wu = payload.work_unit
        wu.refresh_from_db()
        assert wu.num_unsatisfied_requirements == 1

    def test_on_reschedule_one_time(self):
        payload = PeriodicallyCleanOldSolutions.objects.create(period_minutes=None, threshold_days=10)
        assert CleanOldSolutions.objects.count() == 0
        assert PeriodicSolutionRemover().on_reschedule(payload) is None
        assert CleanOldSolutions.objects.count() == 1
        # datetime.datetime.min since we didn't run do_work()
        assert CleanOldSolutions.objects.first().threshold == datetime.datetime.min.replace(
            tzinfo=datetime.timezone.utc
        )
        wu = payload.work_unit
        wu.refresh_from_db()
        assert wu.num_unsatisfied_requirements == 1
