# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

from prometheus_client import Gauge

from toolchain.dependency.constants import ErrorType, PythonResolveRequest, SolutionResult, SolutionStatus
from toolchain.dependency.models import ResolverSolution
from toolchain.satresolver.core import ResolutionError, Resolver
from toolchain.satresolver.graph import PackageError
from toolchain.satresolver.pypi.depgraph import Depgraph
from toolchain.satresolver.pypi.python_config import PythonConfig
from toolchain.satresolver.pypi.python_graph import PythonGraph, PythonRequirements
from toolchain.satresolver.resolve_graph_to_json import resolve_result_to_json

_logger = logging.getLogger(__name__)

RESOLVE_DEPENDENCIES = Gauge(
    name="toolchain_api_resolve_dependencies",
    documentation="Number of dependencies we resolve",
    multiprocess_mode="all",
)


def resolve_dependencies(
    *, depgraph: Depgraph, resolve_request: PythonResolveRequest, requirements: PythonRequirements
) -> SolutionResult:
    parameters = resolve_request.get_parameters()
    result = ResolverSolution.get_or_create(
        dependencies=resolve_request.dependencies,
        parameters=parameters,
        leveldb_version=depgraph.db_version,
        dispatch_async=False,
    )
    solution_id = result.solution_id
    if not result.is_completed:
        resolver_solution = run_resolver(
            depgraph=depgraph,
            solution_id=solution_id,
            requirements=requirements,
            requires_python=resolve_request.python,
            abis=resolve_request.abis,
            platform=resolve_request.platform,
        )
        ResolverSolution.store_solution(
            solution_id=solution_id, solution=resolver_solution.result, error_type=resolver_solution.error_type
        )
        result = resolver_solution
    return result


def run_resolver(
    *,
    depgraph: Depgraph,
    solution_id: str,
    requirements: PythonRequirements,
    requires_python: str,
    abis: set[str],
    platform: str,
) -> SolutionResult:
    RESOLVE_DEPENDENCIES.set(len(requirements))
    try:
        graph = PythonGraph(depgraph, requires_python=requires_python, valid_abis=abis, platform=platform)
        config = PythonConfig.for_requirements(requirements=requirements, graph=graph, override_reqs=True)
        _logger.info(f"run_resolver {config}")
        resolver = Resolver(config)
        resolver.run()
    except PackageError as error:
        _logger.warning(f"Package error, data_version={depgraph.db_version}: {error!r}", exc_info=True)
        return SolutionResult(
            solution_id=solution_id,
            db_version=depgraph.db_version,
            status=SolutionStatus.FAIL,
            error_type=ErrorType.PACKAGE_NOT_FOUND,
            result=error.to_dict(),
        )
    except ResolutionError as error:
        _logger.warning(f"Resolution error, data_version={depgraph.db_version}: {error!r}", exc_info=True)
        return SolutionResult(
            solution_id=solution_id,
            db_version=depgraph.db_version,
            status=SolutionStatus.FAIL,
            error_type=ErrorType.NO_SOLUTION,
            result=error.to_dict(),
        )
    _logger.info(f"run_resolver completed: iterations={resolver.loop_iterations:,} {solution_id=}")
    return SolutionResult(
        solution_id=solution_id,
        db_version=depgraph.db_version,
        status=SolutionStatus.SUCCESS,
        result=resolve_result_to_json(resolver),
    )
