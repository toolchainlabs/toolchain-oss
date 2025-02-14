# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.contrib.admin import ModelAdmin, SimpleListFilter

from toolchain.dependency.models import (
    CleanOldSolutions,
    PeriodicallyCleanOldSolutions,
    ResolveDependencies,
    ResolverSolution,
    SolutionState,
)
from toolchain.toolshed.admin_models.utils import ReadOnlyModelAdmin, pretty_format_json
from toolchain.toolshed.admin_models.workflow_utils import WorkflowPayloadMixin, WorkUnitStateFilter


class SolutionStateFilter(SimpleListFilter):
    title = "state"
    parameter_name = "state"

    def lookups(self, request, model_admin):
        return tuple((val.value, val.value.capitalize()) for val in SolutionState)

    def queryset(self, request, queryset):
        enum_value = self.value()
        if enum_value:
            return queryset.filter(_solution_state=enum_value)
        return queryset


class PeriodicallyCleanOldSolutionsModelAdmin(ReadOnlyModelAdmin, WorkflowPayloadMixin):
    list_display = ("state", "created_at", "succeeded_at", "last_attempt", "period_minutes", "threshold_days")
    fields = ("state", "created_at", "succeeded_at", "last_attempt", "period_minutes", "threshold_days")


class CleanOldSolutionsModelAdmin(ReadOnlyModelAdmin, WorkflowPayloadMixin):
    list_display = ("state", "created_at", "succeeded_at", "last_attempt", "threshold")
    fields = ("state", "created_at", "succeeded_at", "last_attempt", "threshold")


class ResolverSolutionAdmin(ModelAdmin):
    list_display = ("id", "created_at", "leveldb_version", "state")
    list_filter = (SolutionStateFilter,)
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    fields = ("created_at", "state", "last_update", "leveldb_version", "error_type", "result")
    readonly_fields = ("created_at", "leveldb_version", "state", "last_update", "result", "error_type", "state")

    def result(self, obj) -> str:
        result = obj._result
        return pretty_format_json(result) if result else "N/A"

    def state(self, obj) -> str:
        return obj.state.value.capitalize()

    def error_type(self, obj) -> str:
        return obj.error_type.value.capitalize() if obj.error_type else "N/A"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class ResolveDependenciesAdmin(ReadOnlyModelAdmin, WorkflowPayloadMixin):
    list_display = ("state", "created_at", "succeeded_at", "last_attempt")
    fields = ("state", "parameters", "python_requirements", ("created_at", "succeeded_at", "last_attempt"))
    ordering = ("-work_unit__created_at",)
    list_filter = (WorkUnitStateFilter,)

    def python_requirements(self, obj) -> str:
        return pretty_format_json(obj.python_requirements)

    def parameters(self, obj) -> str:
        return pretty_format_json(obj.parameters)


def get_dependency_models():
    return {
        ResolverSolution: ResolverSolutionAdmin,
        PeriodicallyCleanOldSolutions: PeriodicallyCleanOldSolutionsModelAdmin,
        CleanOldSolutions: CleanOldSolutionsModelAdmin,
        ResolveDependencies: ResolveDependenciesAdmin,
    }
