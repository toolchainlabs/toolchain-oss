# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging

from django.http import JsonResponse
from django.views.generic import View

from toolchain.workflow.work_dispatcher import WorkDispatcher

logger = logging.getLogger(__name__)


# Views for the workers themselves.
class WorkerStatusz(View):
    def get(self, request):
        work_dispatcher = WorkDispatcher.singleton
        queued_work_units = [str(wu) for wu in work_dispatcher.get_queued_work_units()]
        return JsonResponse(data={"queued_work_units": queued_work_units})
