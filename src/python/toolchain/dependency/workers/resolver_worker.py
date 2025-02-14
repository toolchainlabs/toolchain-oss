# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging

from django.conf import settings

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.dependency.constants import SolutionResult
from toolchain.dependency.models import ResolveDependencies, ResolverSolution
from toolchain.dependency.python_resolver import run_resolver
from toolchain.satresolver.pypi.depgraph import Depgraph
from toolchain.satresolver.pypi.python_graph import PythonGraph
from toolchain.util.leveldb.dataset import DatasetLoadError
from toolchain.util.leveldb.latest import ordinal_exists
from toolchain.util.leveldb.syncer import Syncer
from toolchain.util.leveldb.urls import leveldb_for_ordinal
from toolchain.workflow.worker import Worker

_logger = logging.getLogger(__name__)


class PythonDependenciesResolver(Worker):
    work_unit_payload_cls = ResolveDependencies

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._base_local_dir = settings.LOCAL_DEPGRAPH_DIR_URL
        self._solution: SolutionResult | None = None
        self._dry_run = settings.DRY_RUN_WORKFLOW_RESOLVE

    def _get_depgraph(self, leveldb_version: int) -> Depgraph | None:
        local_leveldb = ordinal_exists(self._base_local_dir, leveldb_version)
        if not local_leveldb:
            syncer = Syncer(remote_basedir_url=settings.DEPGRAPH_BASE_DIR_URL, local_basedir_url=self._base_local_dir)
            syncer.fetch(leveldb_version)
        _logger.info(f"depgraph={leveldb_version} local={local_leveldb}")
        try:
            return Depgraph.from_url(leveldb_for_ordinal(self._base_local_dir, leveldb_version))
        except DatasetLoadError as error:
            _logger.warning(f"Loading dataset failed {error}")
        return None

    def do_work(self, work_unit_payload: ResolveDependencies) -> bool:
        pending_solution = ResolverSolution.get_by_id(solution_id=work_unit_payload.solution_id)
        if not pending_solution:
            raise ToolchainAssertion(f"Solution not found for {work_unit_payload.solution_id=}")
        requirements = PythonGraph.parse_requirements(work_unit_payload.python_requirements)
        python = work_unit_payload.parameters["python"]
        abis = set(work_unit_payload.parameters["abis"])
        platform = work_unit_payload.parameters["platform"]
        depgraph = self._get_depgraph(pending_solution.leveldb_version)
        if not depgraph:
            return False
        self._solution = run_resolver(
            depgraph=depgraph,
            requirements=requirements,
            requires_python=python,
            abis=abis,
            platform=platform,
            solution_id=work_unit_payload.solution_id,
        )
        return True

    def on_reschedule(self, work_unit_payload: ResolveDependencies) -> datetime.datetime:
        return utcnow()  # Retry immediately

    def on_success(self, work_unit_payload: ResolveDependencies) -> None:
        if not self._solution:
            raise ToolchainAssertion("Solution not saved.")
        _logger.info(f"store_solution solution_id={work_unit_payload.solution_id} dry_run={self._dry_run}")
        if self._dry_run:
            return
        ResolverSolution.store_solution(
            solution_id=work_unit_payload.solution_id,
            solution=self._solution.result,
            error_type=self._solution.error_type,
        )
