# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.crawler.pypi.exceptions import TransientError
from toolchain.crawler.pypi.models import (
    DumpDistributionData,
    PeriodicallyProcessChangelog,
    ProcessChangelog,
    most_recent_complete_serial,
)
from toolchain.crawler.pypi.xmlrpc_api import ApiClient
from toolchain.workflow.worker import Worker

_logger = logging.getLogger(__name__)


class PeriodicChangelogProcessor(Worker):
    work_unit_payload_cls = PeriodicallyProcessChangelog

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._serial_from: int | None = None
        self._serial_to: int | None = None
        self._transient_error = False

    def do_work(self, work_unit_payload: PeriodicallyProcessChangelog) -> bool:
        # Start at the most recent serial we've definitely handled in either an incremental or full crawl.
        if work_unit_payload.period_minutes is None and work_unit_payload.work_unit.requirements.exists():
            # We were a one-time processing, and we've already created our requirement ProcessChangelog, so we're done.
            return True
        self._serial_from = most_recent_complete_serial()
        client = ApiClient()
        try:
            self._serial_to = client.get_last_serial()
        except TransientError as error:
            _logger.warning(f"Error getting latest serial, will retry later. {error!r}")
            self._transient_error = True
        # Note that if we're not a one-time processing we never succeed, but keep scheduling changelog processing forever.
        return False

    def on_reschedule(self, work_unit_payload: PeriodicallyProcessChangelog) -> datetime | None:
        if self._transient_error:
            return utcnow() + timedelta(minutes=5)
        if self._serial_from is None or self._serial_to is None:
            raise ToolchainAssertion(f"change log serials not set. {self._serial_from=} {self._serial_to=}")
        if self._serial_from < self._serial_to:
            pc_work = queue_process_changes(serial_from=self._serial_from, serial_to=self._serial_to)
            work_unit_payload.add_requirement_by_id(pc_work.work_unit_id)
        if work_unit_payload.period_minutes is None:
            return None
        return utcnow() + timedelta(minutes=work_unit_payload.period_minutes)


def queue_process_changes(*, serial_from: int, serial_to: int) -> ProcessChangelog:
    pc_work = ProcessChangelog.create(serial_from=serial_from, serial_to=serial_to)
    dump_work = DumpDistributionData.trigger_incremental(serial_from, serial_to)
    dump_work.add_requirement_by_id(pc_work.work_unit_id)
    return pc_work
