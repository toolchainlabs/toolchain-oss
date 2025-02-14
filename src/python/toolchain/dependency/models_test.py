# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

import pytest
from freezegun import freeze_time

from toolchain.base.datetime_tools import utcnow
from toolchain.dependency.constants import ErrorType, SolutionStatus
from toolchain.dependency.models import (
    MissingSolutionObject,
    PeriodicallyCleanOldSolutions,
    ResolveDependencies,
    ResolverSolution,
)


@pytest.mark.django_db()
class TestResolverSolution:
    def test_create(self) -> None:
        assert ResolverSolution.objects.count() == 0
        assert ResolveDependencies.objects.count() == 0
        resolve_result = ResolverSolution.get_or_create(
            dependencies=["tinsel==1.22.0"],
            parameters={"py": "3.3", "abi": "abi3", "platform": "any"},
            leveldb_version=56110,
        )
        assert resolve_result.solution_id is not None
        assert resolve_result.result == {}
        assert ResolverSolution.objects.count() == 1
        assert ResolveDependencies.objects.count() == 1
        resolve = ResolveDependencies.objects.first()
        solution = ResolverSolution.objects.first()
        assert solution.id == resolve_result.solution_id == resolve.solution_id
        assert solution.state == ResolverSolution.State.PENDING
        assert solution.is_completed is False
        assert solution.last_update is None
        assert solution.created_at.timestamp() == pytest.approx(utcnow().timestamp())
        assert solution.leveldb_version == 56110
        assert solution.parameters_digest == "76837a9680fc51106d5456eefbffb29f9a8d3354728af826c94d7331b4a227a0"
        assert solution.dependencies_digest == "41ed2eb7dc98cee7cafb248fc9224aa6a36125a504e69be5d788edd358646444"
        assert len(solution.parameters_digest) == ResolverSolution._meta.get_field("parameters_digest").max_length == 64
        assert (
            len(solution.dependencies_digest)
            == ResolverSolution._meta.get_field("dependencies_digest").max_length
            == 64
        )
        assert resolve.python_requirements == ["tinsel==1.22.0"]
        assert resolve.parameters == {"py": "3.3", "abi": "abi3", "platform": "any"}

    def test_create_twice(self) -> None:
        assert ResolverSolution.objects.count() == 0
        resolve_result = ResolverSolution.get_or_create(
            dependencies=["tinsel==1.22.0"],
            parameters={"py": "3.3", "abi": "abi3", "platform": "any"},
            leveldb_version=56110,
        )
        assert resolve_result.solution_id is not None
        assert resolve_result.result == {}
        assert ResolverSolution.objects.count() == 1
        assert ResolveDependencies.objects.count() == 1
        solution = ResolverSolution.objects.first()
        assert solution.id == resolve_result.solution_id
        resolve_result_2 = ResolverSolution.get_or_create(
            dependencies=["tinsel==1.22.0"],
            parameters={"py": "3.3", "abi": "abi3", "platform": "any"},
            leveldb_version=56110,
        )
        assert ResolverSolution.objects.count() == 1
        assert ResolveDependencies.objects.count() == 1
        resolve = ResolveDependencies.objects.first()
        assert solution.id == resolve_result_2.solution_id == resolve_result.solution_id == resolve.solution_id

    def test_solve_invalid_id(self) -> None:
        assert ResolverSolution.objects.count() == 0
        with pytest.raises(MissingSolutionObject, match="No solution found for: izzy"):
            ResolverSolution.store_solution("izzy", {"mandelbaum": "Magic"})

    def test_get_by_id(self) -> None:
        assert ResolverSolution.objects.count() == 0
        solution_id = ResolverSolution.get_or_create(
            dependencies=["tinsel==1.22.0"],
            parameters={"py": "3.3", "abi": "abi3", "platform": "any"},
            leveldb_version=98282,
        ).solution_id
        assert ResolverSolution.objects.count() == 1
        solution = ResolverSolution.get_by_id(solution_id)
        assert solution is not None
        assert solution == ResolverSolution.objects.first()
        assert solution.id == solution_id
        assert solution.leveldb_version == 98282
        assert ResolverSolution.get_by_id("jerry") is None
        assert ResolverSolution.get_by_id(solution_id[1:]) is None

    def test_solve(self) -> None:
        assert ResolverSolution.objects.count() == 0
        now = utcnow()
        resolve_result = ResolverSolution.get_or_create(
            dependencies=["tinsel==1.22.0"],
            parameters={"py": "3.3", "abi": "abi3", "platform": "any"},
            leveldb_version=7109,
        )
        assert ResolverSolution.objects.count() == 1
        assert ResolverSolution.objects.first().is_completed is False
        solution_dict = {
            "releases": [{"project_name": "aaa", "version": "1.0.0", "sha256": "close-talker"}],
            "dependencies": [],
        }
        resolve_result = ResolverSolution.store_solution(resolve_result.solution_id, solution_dict)
        assert resolve_result.error_type is None
        assert resolve_result.status == SolutionStatus.SUCCESS
        assert resolve_result.result == solution_dict
        solution = ResolverSolution.objects.first()
        assert solution.state == ResolverSolution.State.FINISHED
        assert solution.is_completed is True
        assert solution.last_update.timestamp() == pytest.approx(now.timestamp())
        assert solution.created_at.timestamp() == pytest.approx(now.timestamp())
        assert solution.leveldb_version == 7109

    def test_solve_twice(self) -> None:
        assert ResolverSolution.objects.count() == 0
        resolve_result = ResolverSolution.get_or_create(
            dependencies=["tinsel==1.22.0"],
            parameters={"py": "3.3", "abi": "abi3", "platform": "any"},
            leveldb_version=7109,
        )
        assert ResolverSolution.objects.count() == 1
        assert ResolveDependencies.objects.count() == 1
        assert ResolverSolution.objects.first().is_completed is False
        solution_dict = {"releases": [{"project_name": "aaa", "version": "1.0.0", "sha256": "no-soup-for-you"}]}
        resolve_result = ResolverSolution.store_solution(resolve_result.solution_id, solution_dict)
        assert resolve_result.error_type is None
        assert resolve_result.status == SolutionStatus.SUCCESS
        solution = ResolverSolution.objects.first()
        assert solution.state == ResolverSolution.State.FINISHED
        assert solution.is_completed is True
        solution_dict = {
            "releases": [{"project_name": "aaa", "version": "22.33.0", "sha256": "i-don't-want-to-be-a-pirate"}]
        }
        existing_solution = ResolverSolution.store_solution(resolve_result.solution_id, solution_dict)
        assert existing_solution.result == {
            "releases": [{"project_name": "aaa", "version": "1.0.0", "sha256": "no-soup-for-you"}]
        }

        assert ResolveDependencies.objects.count() == 1
        assert solution.last_update == ResolverSolution.objects.first().last_update
        solution = ResolverSolution.objects.first()
        assert solution.to_result().result == {
            "releases": [{"project_name": "aaa", "version": "1.0.0", "sha256": "no-soup-for-you"}]
        }

    def test_get_already_solved(self) -> None:
        resolve_result = ResolverSolution.get_or_create(
            dependencies=["tinsel==1.22.0"],
            parameters={"py": "3.3", "abi": "abi3", "platform": "any"},
            leveldb_version=7109,
        )
        resolve_result = ResolverSolution.store_solution(
            resolve_result.solution_id,
            {"releases": [{"project_name": "tinsel", "version": "1.222.33", "sha256": "low-talker"}]},
        )
        assert resolve_result.error_type is None
        assert resolve_result.status == SolutionStatus.SUCCESS
        resolve_result_2 = ResolverSolution.get_or_create(
            dependencies=["tinsel==1.22.0"],
            parameters={"py": "3.3", "abi": "abi3", "platform": "any"},
            leveldb_version=7109,
        )
        assert resolve_result.solution_id == resolve_result_2.solution_id == ResolverSolution.objects.first().id
        assert resolve_result_2.result == {
            "releases": [{"project_name": "tinsel", "version": "1.222.33", "sha256": "low-talker"}]
        }
        assert ResolverSolution.objects.count() == 1
        assert ResolveDependencies.objects.count() == 1

    @pytest.mark.parametrize("error_type", list(ErrorType))
    def test_store_failure(self, error_type) -> None:
        resolve_result = ResolverSolution.get_or_create(
            dependencies=["tinsel==1.22.0"],
            parameters={"py": "3.3", "abi": "abi3", "platform": "any"},
            leveldb_version=7109,
        )
        error_result = {
            "msg": "No matching distributions found for coreschema",
            "package_name": "coreschema",
            "available_versions": [],
        }
        resolve_result = ResolverSolution.store_solution(
            resolve_result.solution_id, solution=error_result, error_type=error_type
        )
        assert resolve_result.error_type == error_type
        assert resolve_result.status == SolutionStatus.FAIL
        assert ResolverSolution.objects.count() == 1
        solution = ResolverSolution.objects.first()
        assert solution.state == ResolverSolution.State.FINISHED
        result = solution.to_result()
        assert result.status == SolutionStatus.FAIL
        assert result.error_type == error_type
        assert result.result == {
            "msg": "No matching distributions found for coreschema",
            "package_name": "coreschema",
            "available_versions": [],
        }
        assert result.solution_id == solution.id

    def _generate_solutions(self, base_time: datetime.datetime, count: int) -> list[str]:
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

    def test_clean_old_solutions(self) -> None:
        base_time = utcnow() - datetime.timedelta(days=20)
        solution_ids = self._generate_solutions(base_time, 30)
        assert ResolverSolution.objects.count() == 30
        assert ResolverSolution.clean_old_solutions(base_time - datetime.timedelta(days=35)) == 0
        assert ResolverSolution.clean_old_solutions(base_time - datetime.timedelta(days=19, hours=4)) == 10
        assert ResolverSolution.objects.count() == 20
        assert set(ResolverSolution.objects.all().values_list("id", flat=True)) == set(solution_ids[:20])


@pytest.mark.django_db()
class TestPeriodicallyCleanOldSolutions:
    def test_create(self) -> None:
        assert PeriodicallyCleanOldSolutions.objects.count() == 0
        PeriodicallyCleanOldSolutions.create_or_update(period_minutes=73, threshold_days=34)
        assert PeriodicallyCleanOldSolutions.objects.count() == 1
        pcos = PeriodicallyCleanOldSolutions.objects.first()
        assert pcos.period_minutes == 73
        assert pcos.threshold_days == 34

    def test_update(self) -> None:
        assert PeriodicallyCleanOldSolutions.objects.count() == 0
        PeriodicallyCleanOldSolutions.create_or_update(period_minutes=73, threshold_days=34)
        assert PeriodicallyCleanOldSolutions.objects.count() == 1
        PeriodicallyCleanOldSolutions.create_or_update(period_minutes=190, threshold_days=43)
        assert PeriodicallyCleanOldSolutions.objects.count() == 1
        pcos = PeriodicallyCleanOldSolutions.objects.first()
        assert pcos.period_minutes == 190
        assert pcos.threshold_days == 43
