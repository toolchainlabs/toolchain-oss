# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import logging

from django.contrib.admin import SimpleListFilter, action
from django.utils.html import format_html

from toolchain.aws.s3 import S3
from toolchain.pants_demos.depgraph.models import DemoRepo, GenerateDepgraphForRepo
from toolchain.toolshed.admin_models.utils import ReadOnlyModelAdmin, pretty_format_json
from toolchain.toolshed.admin_models.workflow_utils import WorkflowPayloadMixin, WorkUnitStateFilter

_logger = logging.getLogger(__name__)


class ProcessingStateFilter(SimpleListFilter):
    title = "state"
    parameter_name = "state"

    def lookups(self, request, model_admin):
        return tuple((val.value, val.display_name) for val in DemoRepo.State)

    def queryset(self, request, queryset):
        enum_value = self.value()
        if enum_value:
            return queryset.filter(_processing_state=enum_value)
        return queryset


class GenerateDepgraphForRepoModelAdmin(ReadOnlyModelAdmin, WorkflowPayloadMixin):
    list_display = ("state", "created_at", "succeeded_at", "last_attempt")
    fields = (
        "state",
        "created_at",
        "succeeded_at",
        "last_attempt",
    )
    list_filter = (WorkUnitStateFilter,)


class DemoRepoAdmin(ReadOnlyModelAdmin):
    list_display = (
        "repo_full_name",
        "created_at",
        "state",
        "num_of_targets",
        "processing_time",
        "last_processed",
        "id",
    )
    list_filter = (ProcessingStateFilter,)
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    search_fields = ("repo_account", "repo_name")
    actions = ("reprocess_repo",)
    fields = (
        (
            "id",
            "repo_full_name",
            "repo_url",
        ),
        ("state", "num_of_targets", "processing_time", "created_at", "last_processed"),
        "errors",
        (
            "result_location",
            "result_json",
        ),
    )

    @action(
        description="Reprocess repo",
    )
    def reprocess_repo(self, request, queryset):
        ids = list(queryset.values_list("id", flat=True))
        queryset.update(_processing_state=DemoRepo.State.NOT_PROCESSED.value)
        _logger.info(f"re-run for {ids}")
        for payload in GenerateDepgraphForRepo.objects.filter(demo_repo_id__in=ids):
            payload.rerun_work_unit()

    def state(self, obj) -> str:
        return obj.processing_state.display_name

    def repo_url(self, obj):
        return format_html("<a href='{url}'>{url}</a>", url=f"https://github.com/{obj.repo_full_name}")

    def get_search_results(self, request, queryset, search_term):
        if "/" in search_term:
            account, _, repo = search_term.partition("/")
            qs = queryset.filter(repo_account__icontains=account, repo_name__icontains=repo)
            if qs.exists():
                return qs, False
        return super().get_search_results(request, queryset, search_term)

    def _get_results_json(self, dr: DemoRepo) -> dict | None:
        result_url = dr.result_location
        if not result_url:
            return None
        s3 = S3()
        bucket, key = s3.parse_s3_url(result_url)
        result_data = s3.get_content_or_none(bucket=bucket, key=key)
        if not result_data:
            return None
        return json.loads(result_data)

    def errors(self, obj: DemoRepo) -> str:
        if not obj.is_failed:
            return "N/A"
        result_data = self._get_results_json(obj)
        if not result_data:
            return "N/A"
        errors_obj = result_data.get("errors", {})
        return "\n".join((f"{key}: {value}" for key, value in errors_obj.items())) or "N/A"

    def result_json(self, obj: DemoRepo) -> str:
        result_data = self._get_results_json(obj)
        return pretty_format_json(result_data) if result_data else "N/A"


def get_pants_demos_models():
    return {
        DemoRepo: DemoRepoAdmin,
        GenerateDepgraphForRepo: GenerateDepgraphForRepoModelAdmin,
    }
