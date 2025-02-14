# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from urllib.parse import urlparse

from django.contrib.admin import TabularInline
from django.db.models import Q

from toolchain.crawler.base.models import FetchURL
from toolchain.crawler.pypi.models import (
    DumpDistributionData,
    PeriodicallyProcessChangelog,
    PeriodicallyUpdateLevelDb,
    ProcessAllProjects,
    ProcessAllProjectsShard,
    ProcessChangelog,
    ProcessChangelogAdded,
    ProcessChangelogRemoved,
    ProcessDistribution,
    ProcessProject,
    ProcessProjectDistribution,
    UpdateLevelDb,
)
from toolchain.django.webresource.models import WebResource, WebResourceLink
from toolchain.packagerepo.pypi.models import Distribution, DistributionData, Project, Release
from toolchain.toolshed.admin_models.utils import ReadOnlyModelAdmin, pretty_format_json, url_as_link
from toolchain.toolshed.admin_models.workflow_utils import WorkflowPayloadMixin


def _get_filename(url: str) -> str:
    return urlparse(url).path.split("/")[-1]


class BasePypiModelAdmin(ReadOnlyModelAdmin):
    pass


class WebResourceAdmin(BasePypiModelAdmin):
    list_display = ("file_name", "freshness", "etag")
    ordering = ("-freshness",)
    search_fields = ("url",)

    def file_name(self, obj) -> str:
        return _get_filename(obj.url)


class WebResourceLinkAdmin(BasePypiModelAdmin):
    pass


class FetchURLAdmin(BasePypiModelAdmin, WorkflowPayloadMixin):
    list_display = (
        "file_name",
        "state",
        "created_at",
        "last_attempt",
        "succeeded_at",
        "last_http_status",
    )
    fields = ("file_name", "url") + WorkflowPayloadMixin.workflow_readonly_fields

    def file_name(self, obj) -> str:
        return _get_filename(obj.url)


class PeriodicallyProcessChangelogAdmin(BasePypiModelAdmin):
    list_display = ("period_minutes",)


class ProcessChangeLogAdmin(BasePypiModelAdmin):
    list_display = ("serial_from", "serial_to", "num_distributions_added", "num_distributions_removed")


class DumpDistributionDataAdmin(BasePypiModelAdmin, WorkflowPayloadMixin):
    list_display = ("state", "created_at", "succeeded_at", "serial_from", "serial_to")
    fields = (
        "state",
        ("shard", "num_shards"),
        ("serial_from", "serial_to"),
        ("key_prefix", "bucket"),
        ("created_at", "succeeded_at"),
        ("last_attempt", "leased_until"),
        ("num_unsatisfied_requirements", "node"),
    )
    readonly_fields = (
        "shard",
        "num_shards",
        "serial_from",
        "serial_to",
        "key_prefix",
        "bucket",
    ) + WorkflowPayloadMixin.workflow_readonly_fields


class PeriodicallyUpdateLevelDbAdmin(BasePypiModelAdmin, WorkflowPayloadMixin):
    list_display = ("builder_cls", "period_minutes", "rebuild", "input_dir_url", "output_dir_base_url")
    fields = (
        "state",
        ("builder_cls", "period_minutes", "rebuild"),
        "input_dir_url",
        "output_dir_base_url",
        ("created_at", "succeeded_at"),
        ("last_attempt", "leased_until"),
        ("num_unsatisfied_requirements", "node"),
    )
    readonly_fields = (
        "builder_cls",
        "period_minutes",
        "input_dir_url",
        "output_dir_base_url",
    ) + WorkflowPayloadMixin.workflow_readonly_fields

    def has_change_permission(self, request, obj=None):
        return obj.work_unit.is_leased if obj else False

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class UpdateLevelDbAdmin(BasePypiModelAdmin, WorkflowPayloadMixin):
    list_display = ("builder_cls", "state", "created_at", "succeeded_at")
    fields = (
        "builder_cls",
        "state",
        ("created_at", "succeeded_at"),
        ("last_attempt", "leased_until"),
        ("num_unsatisfied_requirements", "node"),
        ("input_dir_url", "output_dir_url", "existing_leveldb_dir_url"),
    )
    readonly_fields = ("builder_cls",)


class ProcessChangelogAddedAdmin(BasePypiModelAdmin):
    pass


class ProcessChangelogRemovedAdmin(BasePypiModelAdmin):
    pass


class ProcessDistributionAdmin(BasePypiModelAdmin):
    pass


class ProcessProjectAdmin(BasePypiModelAdmin):
    pass


class ProcessProjectDistributionAdmin(BasePypiModelAdmin):
    pass


class DistributionInline(TabularInline):
    model = Distribution
    max_num = 20
    fields = ("filename", "dist_type", "serial_from", "serial_to", "url")


class ReleaseAdmin(BasePypiModelAdmin):
    list_display = ("project", "version", "url")
    fields = ("project", "version", "url", "release_files")
    search_fields = ("project__name",)
    inlines = (DistributionInline,)

    def project(self, obj):
        return obj.project.name

    def url(self, obj):
        return url_as_link(f"https://pypi.org/project/{obj.project.name}/{obj.version}/")

    def release_files(self, obj):
        return url_as_link(f"https://pypi.org/project/{obj.project.name}/{obj.version}/#files")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("project")


class ReleasesInline(TabularInline):
    model = Release
    max_num = 20
    fields = ("version", "distributions", "release", "files")
    readonly_fields = ("version", "distributions", "release", "files")
    ordering = ("-version",)

    def distributions(self, obj) -> int:
        return obj.distributions.count()

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("project").prefetch_related("distributions")

    def release(self, obj):
        return url_as_link(f"https://pypi.org/project/{obj.project.name}/{obj.version}/")

    def files(self, obj):
        return url_as_link(f"https://pypi.org/project/{obj.project.name}/{obj.version}/#files")


class ProjectAdmin(BasePypiModelAdmin):
    list_display = ("name", "releases_count", "pypi_project")
    fields = ("name", "releases_count", ("pypi_url", "pypi_project"))
    search_fields = ("name",)

    inlines = (ReleasesInline,)

    def get_search_results(self, request, queryset, search_term):
        # Unless * is specified, we try an exact name search first since it is much faster than a LIKE %term% query
        clean_search_term = search_term.replace("*", "")
        if clean_search_term == search_term:
            qs = queryset.filter(name=search_term)
            if qs.exists():
                return qs, False
        return super().get_search_results(request, queryset, clean_search_term)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("releases")

    def releases_count(self, obj) -> int:
        return obj.releases.count()

    def pypi_url(self, obj) -> str:
        return url_as_link(obj.pypi_url)

    def pypi_project(self, obj) -> str:
        return url_as_link(f"https://pypi.org/project/{obj.name}")


class DistributionAdmin(BasePypiModelAdmin):
    list_display = ("project", "version", "dist_type", "filename", "module_count")
    list_filter = ("dist_type",)
    search_fields = ("release__project__name", "filename")
    fields = ("project", "version", "dist_type", "filename", "url", "metadata", "modules")

    def get_search_results(self, request, queryset, search_term):
        # Unless * is specified, we try an exact name search first since it is much faster than a LIKE %term% query
        clean_search_term = search_term.replace("*", "")
        if clean_search_term == search_term:
            qs = queryset.filter(Q(release__project__name=search_term) | Q(filename=search_term))
            if qs.exists():
                return qs, False
        return super().get_search_results(request, queryset, clean_search_term)

    def module_count(self, obj) -> int:
        return len(obj.data.modules)

    def modules(self, obj) -> str:
        return pretty_format_json(obj.data.modules)

    def metadata(self, obj) -> str:
        return pretty_format_json(obj.data.metadata)

    def project(self, obj):
        return obj.release.project.name

    def version(self, obj):
        return obj.release.version

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("release", "release__project", "data")


def get_pypi_models():
    return {
        WebResource: WebResourceAdmin,
        WebResourceLink: WebResourceLinkAdmin,
        DumpDistributionData: DumpDistributionDataAdmin,
        ProcessChangelog: ProcessChangeLogAdmin,
        PeriodicallyProcessChangelog: PeriodicallyProcessChangelogAdmin,
        PeriodicallyUpdateLevelDb: PeriodicallyUpdateLevelDbAdmin,
        UpdateLevelDb: UpdateLevelDbAdmin,
        ProcessChangelogAdded: ProcessChangelogAddedAdmin,
        ProcessChangelogRemoved: ProcessChangelogRemovedAdmin,
        ProcessDistribution: ProcessDistributionAdmin,
        ProcessProject: ProcessProjectAdmin,
        ProcessProjectDistribution: ProcessProjectDistributionAdmin,
        FetchURL: FetchURLAdmin,
        Project: ProjectAdmin,
        Release: ReleaseAdmin,
        Distribution: DistributionAdmin,
        DistributionData: False,
        ProcessAllProjects: False,
        ProcessAllProjectsShard: False,
    }
