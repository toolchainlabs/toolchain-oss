# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import functools
import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass, fields

from django.conf import settings
from django.db.models import Q
from django.forms import CharField, ValidationError
from django.http import Http404, HttpResponseBadRequest
from prometheus_client import Gauge
from rest_framework import viewsets
from rest_framework.response import Response

from toolchain.base.toolchain_error import ToolchainError
from toolchain.dependency.api.serializers import (
    DistributionSerializer,
    ProjectSerializer,
    PythonDistributionSerializer,
    ReleaseSerializer,
)
from toolchain.django.auth.constants import AccessTokenAudience
from toolchain.django.forms.base_form import ToolchainForm
from toolchain.django.util.view_util import BadApiRequest
from toolchain.lang.python.distributions.distribution_key import canonical_project_name
from toolchain.packagerepo.pypi.models import Distribution, DistributionData, Project, Release
from toolchain.users.jwt.authentication import AuthenticationFromInternalHeaders
from toolchain.users.jwt.permissions import AccessTokensPermissions

_logger = logging.getLogger(__name__)


MODULE_DISTRIBUTIONS = Gauge(
    name="toolchain_api_module_distributions",
    documentation="Number of modules distributions queries via the api",
    multiprocess_mode="all",
)


class PackageRepoValidator:
    supported_packagerepos = ["maven", "pypi"]

    @classmethod
    def validate(cls, name):
        if name not in cls.supported_packagerepos:
            raise Http404()
        if name != "pypi":
            raise BadApiRequest(f"API not supported for '{name}'")


class BaseDependencyApiViewSet(viewsets.ViewSet):
    view_type = "app"
    audience = AccessTokenAudience.DEPENDENCY_API
    authentication_classes = (AuthenticationFromInternalHeaders,)
    permission_classes = (AccessTokensPermissions,)


class BaseDependencyApiReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    view_type = "app"
    audience = AccessTokenAudience.DEPENDENCY_API
    authentication_classes = (AuthenticationFromInternalHeaders,)
    permission_classes = (AccessTokensPermissions,)


class PackageRepoViewSet(BaseDependencyApiViewSet):
    lookup_field = "name"

    def list(self, request):
        return Response(PackageRepoValidator.supported_packagerepos)

    def retrieve(self, request, name=None):
        PackageRepoValidator.validate(name)
        return Response({"name": name})


class DistributionsViewSet(BaseDependencyApiViewSet):
    MAX_MODULES = 100

    def list(self, request, packagerepo_name: str):
        PackageRepoValidator.validate(packagerepo_name)
        module_list = request.query_params.get("module_list", "").split(",")
        cleaned_module_list = [module_name.strip() for module_name in module_list if module_name.strip()]
        if not cleaned_module_list or module_list != cleaned_module_list:
            raise BadApiRequest(f"Invalid module list:. {request.query_params.get('module_list', '')}")
        if len(cleaned_module_list) > self.MAX_MODULES:
            raise BadApiRequest(
                f"Exceeded maximum number of modules request (max: {self.MAX_MODULES}, got: {len(cleaned_module_list)})"
            )
        with settings.MODULE_DISTRIBUTION_MAP.get() as mdm:
            modules_map = mdm.get_distributions_for_modules(module_list)
            data_version = mdm.db_version
        results_json = {name: _dists_to_json(dists) for name, dists in modules_map.items()}
        return Response({"results": results_json, "data_version": data_version})


def _dists_to_json(dists: list[Distribution]) -> list[dict]:
    return [{"name": dist.project_name, "version": dist.version} for dist in dists]


class InvalidModuleQuery(ToolchainError):
    pass


@dataclass(frozen=True)
class ModuleQuery:
    filename: str | None = None
    project_name: str | None = None
    version: str | None = None

    def _validate(self):
        if self.filename:
            if self.project_name or self.version:
                raise InvalidModuleQuery("Not allowed to specify project_name and/or version when specifying filename")
        elif not self.project_name:
            raise InvalidModuleQuery("project_name or filename must be specified")

    @classmethod
    def from_string(cls, req_str: str):
        project_name, _, version = req_str.partition("==")
        if not project_name or not version:
            raise InvalidModuleQuery("Invalid requirement string - missing project name and version")
        mq = cls(project_name=project_name, version=version)
        mq._validate()
        return mq

    @classmethod
    def from_json_dict(cls, json_data):
        if not set(json_data.keys()).issubset({fl.name for fl in fields(cls)}):
            raise InvalidModuleQuery("Unrecognized keys")
        mq = cls(**json_data)
        mq._validate()
        return mq

    def __str__(self):
        return f"filename={self.filename}" if self.filename else f"{self.project_name}=={self.version or 'NA'}"

    def to_predicates(self):
        if self.filename:
            return [Q(distribution__filename=self.filename)]
        predicates = [Q(distribution__release__project__name=canonical_project_name(self.project_name))]
        if self.version:
            predicates.append(Q(distribution__release__version=self.version))
        return predicates


class ModulesForm(ToolchainForm):
    MAX_QUERIES = 400
    q = CharField(required=True)

    def _load_text_queries(self, query_str: str) -> list[ModuleQuery]:
        try:
            return [ModuleQuery.from_string(req) for req in query_str.split(",")]
        except InvalidModuleQuery as error:
            raise ValidationError(str(error))

    def _load_json_queries(self, query_str: str) -> list[ModuleQuery]:
        try:
            queries = json.loads(query_str)
        except ValueError:
            raise ValidationError(f"Invalid json in query string: {query_str}")
        if isinstance(queries, dict):
            queries = [queries]
        try:
            return [ModuleQuery.from_json_dict(query) for query in queries]
        except InvalidModuleQuery as error:
            raise ValidationError(str(error))

    def clean_q(self):
        query_str = self.cleaned_data["q"]
        if query_str.startswith("[") or query_str.startswith("{"):
            queries = self._load_json_queries(query_str)
        else:
            queries = self._load_text_queries(query_str)
        if not queries:
            raise ValidationError("Empty queries")
        if len(queries) > self.MAX_QUERIES:
            _logger.warning(f"Max number of queries exceeded ({len(queries)})")
            raise ValidationError(
                f"Exceeded maximum number of queries per request (max: {self.MAX_QUERIES}, got: {len(queries)})"
            )
        return queries


class ModulesViewSet(BaseDependencyApiViewSet):
    def list(self, request, packagerepo_name: str):
        """Return the modules for the query specified in the q param.

        The q param can take one of the following forms:
        - A JSON object containing the following fields: project_name, version (requires project), filename.
        - A JSON list of the above.
        - a comma-separated list of project_name==version strings.
        """
        PackageRepoValidator.validate(packagerepo_name)
        form = ModulesForm(request.query_params)
        if not form.is_valid():
            _logger.warning(f"Bad input in form: {form.errors}")
            return Response({"errors": form.errors.get_json_data()}, status=HttpResponseBadRequest.status_code)
        queries = form.cleaned_data["q"]
        # TODO: ideally, we should label this by repo, but this information is currently not provided via the API.
        MODULE_DISTRIBUTIONS.set(len(queries))

        _logger.info(f"query_modules_distributions queries_count={len(queries)}")

        # Sort results by filename, for consistency.
        results = sorted(
            (_dist_to_dict(dist_data) for dist_data in _get_distributions(queries)), key=lambda x: x["filename"]
        )
        return Response({"results": results})


def _dist_to_dict(dist_data: DistributionData) -> dict:
    dist = dist_data.distribution
    return {
        "project_name": dist.release.project.name,
        "version": dist.release.version,
        "filename": dist.filename,
        "modules": sorted(dist_data.modules),
    }


def _get_distributions(queries: list[ModuleQuery]) -> Iterator[DistributionData]:
    _logger.info(f"Query modules: {','.join(str(mq) for mq in queries)}")
    query_conjunctions = [functools.reduce(lambda a, b: a & b, query.to_predicates()) for query in queries]
    disjunction = functools.reduce(lambda a, b: a | b, query_conjunctions)
    qs = DistributionData.objects.filter(disjunction)
    return qs.select_related("distribution", "distribution__release", "distribution__release__project")


class ProjectsViewSet(BaseDependencyApiReadOnlyViewSet):
    serializer_class = ProjectSerializer
    lookup_field = "name"

    def get_queryset(self):
        PackageRepoValidator.validate(self.kwargs["packagerepo_name"])
        return Project.objects.prefetch_related("releases").order_by("name")


class ReleasesViewSet(BaseDependencyApiReadOnlyViewSet):
    serializer_class = ReleaseSerializer
    lookup_field = "version"
    lookup_value_regex = r"[0-9a-zA-Z\.]{1,100}"

    def get_queryset(self):
        PackageRepoValidator.validate(self.kwargs["packagerepo_name"])
        project_name = canonical_project_name(self.kwargs["project_name"])
        return Release.objects.filter(project__name=project_name).order_by("version")


class ArtifactsViewSet(BaseDependencyApiReadOnlyViewSet):
    serializer_class = DistributionSerializer
    lookup_field = "filename"
    lookup_value_regex = r"[0-9a-zA-Z\.\-\_]{1,300}"

    def get_queryset(self):
        PackageRepoValidator.validate(self.kwargs["packagerepo_name"])
        project_name = canonical_project_name(self.kwargs["project_name"])
        return (
            Distribution.objects.select_related("data")
            .select_related("release")
            .filter(release__project__name=project_name, release__version=self.kwargs["release_version"])
        )


class DependenciesViewSet(BaseDependencyApiViewSet):
    def list(self, request, packagerepo_name, project_name, release_version, artifact_filename):
        PackageRepoValidator.validate(packagerepo_name)
        with settings.DEPGRAPH.get() as depgraph:
            results = depgraph.get_distributions(
                package_name=canonical_project_name(project_name), version=release_version
            )
            return Response({"results": (PythonDistributionSerializer(res).data for res in results)})
