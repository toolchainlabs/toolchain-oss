# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from pathlib import Path

import pytest

from toolchain.base.datetime_tools import utcnow
from toolchain.dependency.constants import ErrorType, SolutionResult, SolutionStatus
from toolchain.dependency.models import ResolveDependencies, ResolverSolution
from toolchain.dependency.workers.resolver_worker import PythonDependenciesResolver
from toolchain.satresolver.test_helpers.pypi_test_data import DistributionsSet
from toolchain.satresolver.test_helpers.pypi_utils import create_fake_depgraph


@pytest.mark.django_db()
class TestPythonDependenciesResolver:
    def _create_fake_remote_leveldb(self, tmp_path: Path, settings, leveldb_version: str):
        fake_remote_dir = tmp_path / "fake_remote_dir"
        input_list_dir = fake_remote_dir / "input_lists"
        db_path = fake_remote_dir / "leveldbs" / leveldb_version
        db_path.mkdir(parents=True)
        input_list_dir.mkdir(parents=True)
        fake_local_dir = tmp_path / "fake_local_dir"
        fake_local_dir.mkdir()
        settings.LOCAL_DEPGRAPH_DIR_URL = f"file://{fake_local_dir.as_posix()}/"
        settings.DEPGRAPH_BASE_DIR_URL = f"file://{fake_remote_dir.as_posix()}/"
        (input_list_dir / leveldb_version).write_text("No soup for you")
        create_fake_depgraph(db_path, *DistributionsSet.dist_set_1)
        return db_path

    def _create_payload(
        self, leveldb_version: int, parameters: dict, dependencies: list[str]
    ) -> tuple[str, ResolveDependencies]:
        solution_id = ResolverSolution.get_or_create(
            dependencies=dependencies, parameters=parameters, leveldb_version=leveldb_version
        ).solution_id
        payload = ResolveDependencies.create_for_solution(
            solution_id=solution_id, requirements=dependencies, parameters=parameters
        )
        return solution_id, payload

    def _run_resolver(self, leveldb_version: int, parameters: dict, dependencies: list[str]) -> SolutionResult:
        solution_id, payload = self._create_payload(leveldb_version, parameters, dependencies)
        worker = PythonDependenciesResolver()
        assert worker._solution is None
        assert worker.do_work(payload) is True
        solution = worker._solution
        assert solution is not None
        assert solution.solution_id == solution_id
        return solution

    def test_resolve_success(self, tmp_path: Path, settings) -> None:
        self._create_fake_remote_leveldb(tmp_path, settings, "77362")
        solution = self._run_resolver(
            leveldb_version=77362,
            parameters={"python": "3.3", "abis": ["abi3"], "platform": "macosx_10_15_x86_64"},
            dependencies=["aaa==1.0.0"],
        )
        assert solution.status == SolutionStatus.SUCCESS
        assert solution.error_type is None
        assert solution.result == {
            "releases": [
                {
                    "project_name": "aaa",
                    "version": "1.0.0",
                    "sha256": "1a26beecf47250fc1f4a61d6dcaa76fc8ab1a8937d221bb2aad0cff8a3f9cd24",
                }
            ],
            "dependencies": [],
        }

    def test_resolve_fail_missing_transitive_dependency(self, tmp_path: Path, settings) -> None:
        self._create_fake_remote_leveldb(tmp_path, settings, "77362")
        solution = self._run_resolver(
            leveldb_version=77362,
            parameters={"python": "3.3", "abis": ["abi3"], "platform": "macosx_10_15_x86_64"},
            dependencies=["coreschema==0.3.22"],
        )
        assert solution.status == SolutionStatus.FAIL
        assert solution.error_type == ErrorType.NO_SOLUTION
        assert len(solution.result) == 1
        assert solution.result["msg"].startswith(
            "Because Incompatibility(NoVersionsCause, [VersionConstraint(coreschema"
        )

    @pytest.mark.xfail(reason="https://github.com/toolchainlabs/toolchain/issues/5398", strict=True)
    def test_resolve_fail_duplicate_direct_dependencies(self, tmp_path: Path, settings) -> None:
        self._create_fake_remote_leveldb(tmp_path, settings, "77362")
        solution = self._run_resolver(
            leveldb_version=77362,
            parameters={"python": "3.3", "abis": ["abi3"], "platform": "macosx_10_15_x86_64"},
            dependencies=["aaa<=1", "aaa>=2"],
        )
        assert solution.status == SolutionStatus.FAIL
        assert solution.error_type == ErrorType.NO_SOLUTION
        assert len(solution.result) == 1
        assert solution.result["msg"].startswith(
            "Multiple constraints for project aaa. Please specify each project only once."
        )

    def test_leveldb_access_failure(self, tmp_path: Path, settings) -> None:
        db_path = self._create_fake_remote_leveldb(tmp_path, settings, "88312")
        _, payload = self._create_payload(
            leveldb_version=88312,
            parameters={"python": "3.8", "abis": ["abi3"], "platform": "macosx_10_15_x86_64"},
            dependencies=["aaa==1.0.0"],
        )
        db_file = next(fl for fl in db_path.iterdir() if fl.suffix == ".ldb")
        db_file.unlink()  # Trigger a DataLoadError
        worker = PythonDependenciesResolver()
        assert worker.do_work(payload) is False
        assert worker.on_reschedule(payload).timestamp() == pytest.approx(utcnow().timestamp())
