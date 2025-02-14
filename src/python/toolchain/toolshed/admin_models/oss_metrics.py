# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

from toolchain.oss_metrics.bugout_integration.models import DownloadBugoutDataForDay, ScheduleBugoutDataDownload
from toolchain.oss_metrics.models import (
    ScheduleAnonymouseTelemetryProcessing,
    ScheduleUpsertGithubRepoStats,
    UpsertGithubRepoStatsForDay,
    UpsertPantsTelemetryForDay,
)
from toolchain.toolshed.admin_models.utils import ReadOnlyModelAdmin
from toolchain.toolshed.admin_models.workflow_utils import WorkflowPayloadMixin, WorkUnitStateFilter

_logger = logging.getLogger(__name__)


class ScheduleBugoutDataDownloadModelAdmin(ReadOnlyModelAdmin, WorkflowPayloadMixin):
    list_display = (
        "journal_id",
        "period_minutes",
        "state",
        "created_at",
        "succeeded_at",
        "last_attempt",
    )
    fields = (
        ("journal_id", "period_minutes"),
        (
            "state",
            "created_at",
            "succeeded_at",
            "last_attempt",
        ),
    )
    list_filter = (WorkUnitStateFilter,)


class DownloadBugoutDataForDayModelAdmin(ReadOnlyModelAdmin, WorkflowPayloadMixin):
    list_display = (
        "journal_id",
        "day",
        "state",
        "created_at",
        "succeeded_at",
        "last_attempt",
    )
    fields = (
        ("journal_id", "day"),
        (
            "state",
            "created_at",
            "succeeded_at",
            "last_attempt",
        ),
    )
    list_filter = (WorkUnitStateFilter,)


class UpsertPantsTelemetryForDayModelAdmin(ReadOnlyModelAdmin, WorkflowPayloadMixin):
    list_display = (
        "journal_id",
        "day",
        "state",
        "created_at",
        "succeeded_at",
        "last_attempt",
    )
    fields = (
        ("journal_id", "day"),
        (
            "state",
            "created_at",
            "succeeded_at",
            "last_attempt",
        ),
    )
    list_filter = (WorkUnitStateFilter,)


class UpsertGithubRepoStatsForDayModelAdmin(ReadOnlyModelAdmin, WorkflowPayloadMixin):
    list_display = (
        "customer_id",
        "repo_id",
        "day",
        "state",
        "created_at",
        "succeeded_at",
        "last_attempt",
    )
    fields = (
        ("customer_id", "repo_id", "day"),
        (
            "state",
            "created_at",
            "succeeded_at",
            "last_attempt",
        ),
    )
    list_filter = (WorkUnitStateFilter,)


def get_oss_metrics_models():
    return {
        ScheduleBugoutDataDownload: ScheduleBugoutDataDownloadModelAdmin,
        DownloadBugoutDataForDay: DownloadBugoutDataForDayModelAdmin,
        UpsertPantsTelemetryForDay: UpsertPantsTelemetryForDayModelAdmin,
        UpsertGithubRepoStatsForDay: UpsertGithubRepoStatsForDayModelAdmin,
        ScheduleUpsertGithubRepoStats: ReadOnlyModelAdmin,
        ScheduleAnonymouseTelemetryProcessing: ReadOnlyModelAdmin,
    }
