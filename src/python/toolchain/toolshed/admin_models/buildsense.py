# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

from django.contrib.admin import SimpleListFilter, display
from django.contrib.admin.options import IncorrectLookupParameters, ModelAdmin
from humanize import naturaldelta

from toolchain.buildsense.ingestion.models import (
    ConfigureRepoMetricsBucket,
    IndexPantsMetrics,
    MoveBuild,
    ProcessBuildDataRetention,
    ProcessPantsRun,
    ProcessQueuedBuilds,
    RunState,
)
from toolchain.django.site.models import Repo
from toolchain.toolshed.admin_models.utils import ReadOnlyModelAdmin
from toolchain.toolshed.admin_models.workflow_utils import WorkflowPayloadMixin, WorkUnitStateFilter


class RunStateFilter(SimpleListFilter):
    title = "Run state"
    parameter_name = "run_satate"

    def lookups(self, request, model_admin):
        return ((None, "Active"), ("deleted", "Deleted"), ("all", "All"))

    def choices(self, changelist):
        for lookup, title in self.lookup_choices:
            yield {
                "selected": self.value() == lookup,
                "query_string": changelist.get_query_string({self.parameter_name: lookup}, []),
                "display": title,
            }

    def queryset(self, request, queryset):
        value = self.value()
        if value is None:
            return queryset.filter(_run_state=RunState.ACTIVE.value)
        if value == "all":
            return queryset
        if value == "no":
            return queryset.filter(_run_state=RunState.DELETED.value)
        raise IncorrectLookupParameters(f"Invalid queryset filter value: {value}")


class ProcessQueuedBuildsModelAdmin(ReadOnlyModelAdmin, WorkflowPayloadMixin):
    list_display = (
        "state",
        "num_of_builds",
        "created_at",
        "succeeded_at",
        "last_attempt",
    )
    fields = (
        "key",
        "bucket",
        "num_of_builds",
        ("customer_slug", "repo_slug"),
        "state",
        "created_at",
        "succeeded_at",
        "last_attempt",
    )
    list_filter = (WorkUnitStateFilter,)

    # Don't include this property in list_display since it will cause a n+1 DB access issue.
    def customer_slug(self, obj: ProcessQueuedBuilds) -> str:
        return self._get_repo(obj).customer.slug

    # Don't include this property in list_display since it will cause a n+1 DB access issue.
    def repo_slug(self, obj: ProcessQueuedBuilds) -> str:
        return self._get_repo(obj).slug

    def _get_repo(self, obj: ProcessQueuedBuilds) -> Repo:
        return Repo.objects.get(id=obj.repo_id)


class ProcessPantsRunModelAdmin(ReadOnlyModelAdmin, WorkflowPayloadMixin):
    list_display = (
        "state",
        "created_at",
        "succeeded_at",
        "last_attempt",
        "is_active",
    )
    fields = (
        ("state", "is_active"),
        ("customer_slug", "repo_slug"),
        "run_id",
        "created_at",
        "succeeded_at",
        "last_attempt",
    )
    list_filter = (WorkUnitStateFilter, RunStateFilter)

    # Don't include this property in list_display since it will cause a n+1 DB access issue.
    def customer_slug(self, obj: ProcessPantsRun) -> str:
        return self._get_repo(obj).customer.slug

    # Don't include this property in list_display since it will cause a n+1 DB access issue.
    def repo_slug(self, obj: ProcessPantsRun) -> str:
        return self._get_repo(obj).slug

    def _get_repo(self, obj: ProcessPantsRun) -> Repo:
        return Repo.objects.get(id=obj.repo_id)

    @display(boolean=True)
    def is_active(self, obj: ProcessPantsRun) -> bool:
        return not obj.is_deleted


class IndexPantsMetricsModelAdmin(ReadOnlyModelAdmin, WorkflowPayloadMixin):
    list_display = (
        "state",
        "created_at",
        "succeeded_at",
        "last_attempt",
        "is_active",
    )
    fields = (
        ("state", "is_active"),
        ("customer_slug", "repo_slug"),
        "run_id",
        "created_at",
        "succeeded_at",
        "last_attempt",
    )
    list_filter = (WorkUnitStateFilter, RunStateFilter)

    # Don't include this property in list_display since it will cause a n+1 DB access issue.
    def customer_slug(self, obj) -> str:
        return self._get_repo(obj).customer.slug

    # Don't include this property in list_display since it will cause a n+1 DB access issue.
    def repo_slug(self, obj: IndexPantsMetrics) -> str:
        return self._get_repo(obj).slug

    def _get_repo(self, obj: IndexPantsMetrics) -> Repo:
        return Repo.objects.get(id=obj.repo_id)

    @display(boolean=True)
    def is_active(self, obj: IndexPantsMetrics) -> bool:
        return not obj.is_deleted


class ProcessBuildDataRetentionModelAdmin(ModelAdmin, WorkflowPayloadMixin):
    list_display = (
        "repo_fn",
        "dry_run",
        "retention_days",
        "period",
        "state",
        "created_at",
        "succeeded_at",
        "last_attempt",
    )
    fields = (
        ("customer_slug", "repo_slug"),
        ("period_minutes", "retention_days", "dry_run"),
        ("state", "created_at"),
        (
            "succeeded_at",
            "last_attempt",
        ),
    )
    list_filter = (WorkUnitStateFilter,)
    readonly_fields = (
        "customer_slug",
        "repo_slug",
        "state",
        "created_at",
        "succeeded_at",
        "last_attempt",
    )

    def has_delete_permission(self, request, obj: ProcessBuildDataRetention | None = None) -> bool:
        return False

    def has_add_permission(self, request) -> bool:
        return False

    # Don't include this property in list_display since it will cause a n+1 DB access issue.
    def customer_slug(self, obj: ProcessBuildDataRetention) -> str:
        repo = self._add_repo(obj)
        return repo.customer.slug

    # Don't include this property in list_display since it will cause a n+1 DB access issue.
    def repo_slug(self, obj: ProcessBuildDataRetention) -> str:
        repo = self._add_repo(obj)
        return repo.slug

    def period(self, obj: ProcessBuildDataRetention) -> str:
        if not obj.period_minutes:
            return "N/A"
        return naturaldelta(datetime.timedelta(minutes=obj.period_minutes))

    def _add_repo(self, obj: ProcessBuildDataRetention) -> Repo:
        if not hasattr(obj, "__repo"):
            obj.__repo = Repo.get_for_id_or_none(  # pylint: disable=unused-private-member
                repo_id=obj.repo_id, include_inactive=True
            )
        return obj.__repo

    @display(description="Repo")
    def repo_fn(self, obj: ProcessBuildDataRetention) -> str:
        return f"{self.customer_slug(obj)}/{self.repo_slug(obj)}"


def get_buildsense_models():
    return {
        ProcessPantsRun: ProcessPantsRunModelAdmin,
        ProcessQueuedBuilds: ProcessQueuedBuildsModelAdmin,
        IndexPantsMetrics: IndexPantsMetricsModelAdmin,
        ProcessBuildDataRetention: ProcessBuildDataRetentionModelAdmin,
        # Default admin UI for now, still needs to be customized.
        MoveBuild: ReadOnlyModelAdmin,
        ConfigureRepoMetricsBucket: ReadOnlyModelAdmin,
    }
