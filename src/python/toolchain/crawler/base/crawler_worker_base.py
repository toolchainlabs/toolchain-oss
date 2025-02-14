# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

from toolchain.aws.errors import is_transient_aws_error
from toolchain.crawler.base.schedule_util import ScheduleUtil
from toolchain.workflow.constants import WorkExceptionCategory
from toolchain.workflow.models import WorkUnitPayload
from toolchain.workflow.worker import Worker


class CrawlerWorkerBase(Worker):
    """Base class for workers that do crawl work."""

    # Subclasses can override with a subclass of ScheduleUtil, to provide more scheduling functions.
    schedule_util_cls = ScheduleUtil

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._schedule_util = self.schedule_util_cls()

    @property
    def schedule_util(self):
        return self._schedule_util

    def classify_error(self, exception: Exception) -> WorkExceptionCategory | None:
        if is_transient_aws_error(exception):
            return WorkExceptionCategory.TRANSIENT
        return None

    def transient_error_retry_delay(
        self, work_unit_payload: WorkUnitPayload, exception: Exception
    ) -> datetime.timedelta | None:
        # Crawl is not time critical, so it is better to back of for a few minutes and let things recover.
        return datetime.timedelta(minutes=8)
