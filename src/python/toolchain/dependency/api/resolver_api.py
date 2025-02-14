# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

from django.conf import settings
from django.forms import BooleanField, CharField, ValidationError
from django.http import Http404, HttpResponseBadRequest
from pkg_resources import Requirement
from pkg_resources.extern.packaging.requirements import InvalidRequirement  # pylint: disable=import-error
from rest_framework.response import Response

from toolchain.dependency.api.views import BaseDependencyApiViewSet, PackageRepoValidator
from toolchain.dependency.constants import ErrorType, PythonResolveRequest, SolutionResult, SolutionStatus
from toolchain.dependency.models import ResolverSolution
from toolchain.django.forms.base_form import ToolchainForm
from toolchain.django.util.view_util import BadApiRequest
from toolchain.lang.python.distributions.distribution_key import canonical_project_name
from toolchain.packagerepo.pypi.models import Distribution
from toolchain.satresolver.graph import InvalidRequirementsError
from toolchain.satresolver.pypi.python_graph import PythonGraph, get_abi_for_python_version

_logger = logging.getLogger(__name__)


class ResolverForm(ToolchainForm):
    MAX_REQS = 200
    abi = CharField(required=False)
    dependencies = CharField(required=True)
    py = CharField(required=True)
    platform = CharField(required=True)
    u = BooleanField(required=False)

    def clean_abi(self):
        return self.data.get("abi")

    def _canonical_req(self, dependency: str) -> str:
        try:
            req = Requirement.parse(dependency)
        except InvalidRequirement as error:
            raise ValidationError(str(error))
        req.name = canonical_project_name(req.name)  # type: ignore[attr-defined]
        return str(req)

    def _get_dependencies(self) -> list[str]:
        dependencies = self.data["dependencies"]
        if not isinstance(dependencies, list):
            raise ValidationError(f"Invalid dependencies param {dependencies}")
        return dependencies

    def clean_dependencies(self):
        dependencies = self._get_dependencies()
        if len(dependencies) > self.MAX_REQS:
            raise ValidationError(
                message=f"Exceeded maximum number of dependencies per request (max: {self.MAX_REQS}, got: {len(dependencies)})",
                code="invalid",
            )
        return [self._canonical_req(dep) for dep in dependencies]

    def get_resolve_request(self) -> PythonResolveRequest:
        data = self.cleaned_data
        python_version = data["py"]
        abis = set(data["abi"] or get_abi_for_python_version(python_version))
        return PythonResolveRequest(
            dependencies=data["dependencies"], python=python_version, platform=data["platform"], abis=abis
        )


class ResolveViewSet(BaseDependencyApiViewSet):
    _ERROR_TYPE_TO_HTTP_ERROR = {
        ErrorType.PACKAGE_NOT_FOUND: 406,  # HTTP 406 Not Acceptable
        ErrorType.INVALID_REQUIREMENT: 406,  # HTTP 406 Not Acceptable
        ErrorType.NO_SOLUTION: 409,  # HTTP 409 Conflict
    }

    def create(self, request, packagerepo_name: str):
        PackageRepoValidator.validate(packagerepo_name)
        form = ResolverForm(request.data)
        if not form.is_valid():
            _logger.warning(f"Bad input in form: {form.errors}")
            return Response({"errors": form.errors.get_json_data()}, status=HttpResponseBadRequest.status_code)
        resolve_request = form.get_resolve_request()
        with_urls = False

        try:
            PythonGraph.parse_requirements(resolve_request.dependencies)
        except InvalidRequirementsError as error:
            raise BadApiRequest(str(error))
        parameters = resolve_request.get_parameters()
        with settings.DEPGRAPH.get() as depgraph:
            leveldb_version = depgraph.db_version
        solution = ResolverSolution.get_or_create(
            dependencies=resolve_request.dependencies,
            parameters=parameters,
            leveldb_version=leveldb_version,
            dispatch_async=True,
        )
        return self._solution_to_response(solution, with_urls)

    def retrieve(self, request, packagerepo_name: str, pk: str):
        solution_id = pk
        solution = ResolverSolution.get_by_id(solution_id)
        if not solution:
            _logger.warning(f"Unknown {solution_id=}")
            raise Http404()
        return self._solution_to_response(solution.to_result(), False)

    def _solution_to_response(self, solution: SolutionResult, with_urls: bool) -> Response:
        if not solution.is_completed:
            return Response({"solution": {"id": solution.solution_id, "state": ResolverSolution.State.PENDING.value}})
        results = solution.result
        if solution.status == SolutionStatus.FAIL:
            return Response(
                {"error": results, "data_version": solution.db_version},
                status=self._ERROR_TYPE_TO_HTTP_ERROR[solution.error_type],  # type: ignore
            )
        if with_urls:
            Distribution.get_urls(results["releases"])
        results["data_version"] = solution.db_version
        return Response(results)
