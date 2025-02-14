# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import csv
import itertools

import requests
from django.http import StreamingHttpResponse
from django.urls import re_path
from django.views import View

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.db.transaction_broker import TransactionBroker
from toolchain.django.webresource.views import WebResourceDetail
from toolchain.packagerepo.maven.artifact_locator import ArtifactLocator
from toolchain.packagerepo.maven.coordinates import GAVCoordinates
from toolchain.packagerepo.maven.models import POM, MavenArtifact, MavenArtifactVersion, MavenDependency, MavenStats
from toolchain.workflow.admin_views import WorkflowAjaxView, WorkflowDetailsView, WorkflowTemplateView, WorkflowView

transaction = TransactionBroker("packagerepomaven")


class MavenSummary(WorkflowTemplateView):
    template_name = "maven/summary.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            {
                "stats": MavenStats.for_scope(""),
                "num_groups": MavenArtifact.objects.values("group_id").distinct().count(),
            }
        )
        return ctx


class GroupList(WorkflowTemplateView):
    """List all Maven groups."""

    template_name = "maven/group_list.html"


class GroupArtifacts(WorkflowTemplateView):
    """List all artifacts in a group."""

    template_name = "maven/group_artifacts.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        group_id = self.kwargs.get("group_id")
        ctx["group_id"] = group_id
        ctx["stats"] = MavenStats.for_scope(group_id)
        ctx["artifacts"] = MavenArtifact.objects.filter(group_id=group_id)
        return ctx


class MavenArtifactDetail(WorkflowDetailsView):
    """Show details of a single artifact."""

    model = MavenArtifact

    def get_object(self, queryset=None):
        queryset = queryset or self.get_queryset()
        return queryset.get(group_id=self.kwargs.get("group_id"), artifact_id=self.kwargs.get("artifact_id"))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        group_id = self.kwargs.get("group_id")
        artifact_id = self.kwargs.get("artifact_id")
        ctx["stats"] = MavenStats.for_scope(f"{group_id}:{artifact_id}")
        return ctx


class MavenArtifactVersionDetail(WorkflowDetailsView):
    """Show details of a single artifact version."""

    model = MavenArtifactVersion

    def get_object(self, queryset=None):
        queryset = queryset or self.get_queryset()
        try:
            return queryset.get(
                artifact__group_id=self.kwargs.get("group_id"),
                artifact__artifact_id=self.kwargs.get("artifact_id"),
                version=self.kwargs.get("version"),
            )
        except self.model.DoesNotExist:
            coords = GAVCoordinates(
                self.kwargs.get("group_id"), self.kwargs.get("artifact_id"), self.kwargs.get("version")
            )
            pom_url = ArtifactLocator.pom_url(coords)
            if not requests.head(pom_url).ok:
                raise ToolchainAssertion(f"No such artifact version: Expected POM file at {pom_url} not found.")
            return self.model.for_coordinates(coords)


class POMDetail(WorkflowDetailsView):
    """Show details of a single POM."""

    model = POM


class GroupListData(WorkflowAjaxView):
    """AJAX view for a paginated list of groups."""

    def get_ajax_data(self):
        offset = int(self.request.GET.get("offset", 0))
        limit = int(self.request.GET.get("limit", 25))
        order = self.request.GET.get("order")
        search = self.request.GET.get("search")

        sort_field = "group_id"
        if order == "desc":
            sort_field = f"-{sort_field}"

        qs = MavenArtifact.objects.all()
        if search:
            qs = qs.filter(group_id__regex=search)
        total = qs.count()

        group_id_dicts = qs.order_by(sort_field).values("group_id").distinct()[offset : offset + limit]
        ret = {"total": total, "rows": list(group_id_dicts)}
        return ret


class DataDumps(WorkflowTemplateView):
    """Links to available data dumps."""

    template_name = "maven/data_dumps.html"


class DumpDataView(WorkflowView, View):
    """Base class for views that dump data in .csv format."""

    class Echo:
        def write(self, value):
            return value

    def get_filename(self):
        raise NotImplementedError()

    def get_header(self):
        raise NotImplementedError()

    def get_data(self):
        raise NotImplementedError()

    def get(self, request, *args, **kwargs):
        rows = itertools.chain([self.get_header()], self.get_data())
        writer = csv.writer(DumpModelView.Echo())
        response = StreamingHttpResponse((writer.writerow(row) for row in rows), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{self.get_filename()}"'
        return response


class DumpModelView(DumpDataView):
    """Base class for views that dump model instances in .csv format."""

    # Subclasses must set.
    model_cls = None

    # Subclasses may set.  Defaults to all non-relation fields.
    fields: tuple = tuple()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._header = tuple(f.name for f in self._get_fields())

    def get_filename(self):
        return f"{self.model_cls.__name__}.csv"

    def get_header(self):
        return self._header

    def get_data(self):
        return self.model_cls.objects.values_list(*self._header)

    @classmethod
    def _get_fields(cls):
        if cls.fields:
            return [f for f in cls.model_cls._meta.get_fields() if f.name in cls.fields]
        return [
            f
            for f in cls.model_cls._meta.get_fields()
            if not f.is_relation or f.one_to_one or (f.many_to_one and f.related_model)
        ]


class DumpMavenArtifacts(DumpDataView):
    def get_filename(self):
        return "maven_artifacts.csv"

    def get_header(self):
        return ["id", "coordinates"]

    def get_data(self):
        with transaction.atomic():
            for pk, gid, aid in (
                MavenArtifact.objects.using("direct").all().values_list("pk", "group_id", "artifact_id").iterator()
            ):
                yield [pk, f"{gid}:{aid}"]


class DumpMavenArtifactDependencies(DumpDataView):
    def get_filename(self):
        return "maven_artifact_dependencies.csv"

    def get_header(self):
        return ["src_id", "tgt_id"]

    def get_data(self):
        with transaction.atomic():
            yield from MavenDependency.objects.using("direct").all().values_list(
                "dependent__artifact_id", "depends_on_artifact_id"
            ).distinct().iterator()


def get_maven_package_repo_urls(db_name: str):
    maven_package_repo_urls = [
        re_path(r"^summary/$", MavenSummary.as_view(db_name=db_name), name="summary"),
        re_path(r"^groups/$", GroupList.as_view(db_name=db_name), name="group_list"),
        re_path(r"^artifacts/(?P<group_id>[^/]+)/$", GroupArtifacts.as_view(db_name=db_name), name="group_artifacts"),
        re_path(
            r"^artifacts/(?P<group_id>[^/]+)/(?P<artifact_id>[^/]+)/$",
            MavenArtifactDetail.as_view(db_name=db_name),
            name="mavenartifact_detail",
        ),
        re_path(
            r"^artifacts/(?P<group_id>[^/]+)/(?P<artifact_id>[^/]+)/(?P<version>[^/]+)/$",
            MavenArtifactVersionDetail.as_view(),
            name="mavenartifactversion_detail",
        ),
        re_path(
            r"^webresource/(?P<pk>[^/]+)/$", WebResourceDetail.as_view(db_name=db_name), name="mavenwebresource_detail"
        ),
        re_path(r"^pom/(?P<pk>[^/]+)/$", POMDetail.as_view(db_name=db_name), name="pom_detail"),
        re_path(r"^groups/data/$", GroupListData.as_view(db_name=db_name), name="group_list_data"),
        re_path(r"^dump/$", DataDumps.as_view(db_name=db_name), name="data_dumps"),
        re_path(r"^dump/MavenArtifacts.csv$", DumpMavenArtifacts.as_view(db_name=db_name), name="dump_maven_artifacts"),
        re_path(
            r"^dump/MavenArtifactDependencies.csv$",
            DumpMavenArtifactDependencies.as_view(db_name=db_name),
            name="dump_maven_artifact_dependencies",
        ),
    ]
    return maven_package_repo_urls
