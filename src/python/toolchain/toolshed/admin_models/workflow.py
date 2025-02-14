# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.toolshed.admin_models.utils import ReadOnlyModelAdmin
from toolchain.workflow.models import (
    WorkExceptionLog,
    WorkUnit,
    WorkUnitPayload,
    WorkUnitRequirement,
    WorkUnitStateCount,
    WorkUnitStateCountDelta,
)


class BaseWorkflowModelAdmin(ReadOnlyModelAdmin):
    pass


class WorkUnitAdmin(BaseWorkflowModelAdmin):
    list_display = ["id", "payload_ctype", "created_at", "state", "num_unsatisfied_requirements"]
    list_filter = ["state"]


class WorkExceptionLogAdmin(BaseWorkflowModelAdmin):
    list_display = ["id", "category", "timestamp"]
    list_filter = ["category"]
    date_hierarchy = "timestamp"


_WORKFLOW_MODELS = {
    WorkUnit: WorkUnitAdmin,
    WorkExceptionLog: WorkExceptionLogAdmin,
    WorkUnitPayload: False,
    WorkUnitStateCountDelta: False,
    WorkUnitStateCount: False,
    WorkUnitRequirement: False,
}


def get_workflow_models():
    return _WORKFLOW_MODELS
