# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

from django.contrib.admin import SimpleListFilter

from toolchain.workflow.models import WorkUnit


class WorkUnitStateFilter(SimpleListFilter):
    title = "state"
    parameter_name = "state"

    def lookups(self, request, model_admin):
        return WorkUnit.STATE_CHOICES

    def queryset(self, request, queryset):
        state_value = self.value()
        if state_value:
            return queryset.filter(work_unit__state=state_value)
        return queryset


class WorkflowPayloadMixin:
    workflow_readonly_fields = (
        "state",
        "last_attempt",
        "leased_until",
        "node",
        "succeeded_at",
        "created_at",
        "num_unsatisfied_requirements",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("work_unit")

    def state(self, obj) -> str:
        return obj.work_unit.state_str()

    def created_at(self, obj) -> datetime.datetime:
        return obj.work_unit.created_at

    def succeeded_at(self, obj) -> datetime.datetime | None:
        return obj.work_unit.succeeded_at

    def leased_until(self, obj) -> datetime.datetime | None:
        return obj.work_unit.leased_until

    def last_attempt(self, obj) -> datetime.datetime | None:
        return obj.work_unit.last_attempt

    def num_unsatisfied_requirements(self, obj) -> int:
        return obj.work_unit.num_unsatisfied_requirements

    def node(self, obj) -> str:
        return obj.work_unit.node or "N/A"
