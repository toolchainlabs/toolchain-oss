# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging

from toolchain.base.datetime_tools import utcnow
from toolchain.dependency.models import CleanOldSolutions, PeriodicallyCleanOldSolutions, ResolverSolution
from toolchain.workflow.worker import Worker

_logger = logging.getLogger(__name__)


class OldSolutionRemover(Worker):
    work_unit_payload_cls = CleanOldSolutions

    def do_work(self, work_unit_payload: CleanOldSolutions) -> bool:
        solutions_deleted = ResolverSolution.clean_old_solutions(work_unit_payload.threshold)
        _logger.info(f"{solutions_deleted=} threshold_date={work_unit_payload.threshold.isoformat()}")
        return True


class PeriodicSolutionRemover(Worker):
    work_unit_payload_cls = PeriodicallyCleanOldSolutions

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._threshold_date = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)

    def do_work(self, work_unit_payload: PeriodicallyCleanOldSolutions) -> bool:
        self._threshold_date = utcnow() - datetime.timedelta(days=work_unit_payload.threshold_days)
        if work_unit_payload.period_minutes is None and work_unit_payload.work_unit.requirements.exists():
            # We were a one-time processing, and we've already created our requirement OldSolutionRemover, so we're done.
            return True

        # Note that if we're not a one-time processing we never succeed, but keep scheduling changelog processing forever.
        return False

    def on_reschedule(self, work_unit_payload) -> datetime.datetime | None:
        clean_old_work = CleanOldSolutions.create(self._threshold_date)
        work_unit_payload.add_requirement_by_id(clean_old_work.work_unit_id)
        if work_unit_payload.period_minutes is None:
            return None
        return utcnow() + datetime.timedelta(minutes=work_unit_payload.period_minutes)
