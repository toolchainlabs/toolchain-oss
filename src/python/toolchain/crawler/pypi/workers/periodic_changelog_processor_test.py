# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime

import pytest

from toolchain.base.datetime_tools import utcnow
from toolchain.crawler.pypi.models import DumpDistributionData, PeriodicallyProcessChangelog, ProcessChangelog
from toolchain.crawler.pypi.workers.periodic_changelog_processor import (
    PeriodicChangelogProcessor,
    queue_process_changes,
)


@pytest.mark.django_db()
class TestPeriodicChangelogProcessor:
    def test_on_reschedule_on_error(self):
        worker = PeriodicChangelogProcessor()
        payload = PeriodicallyProcessChangelog.objects.create(period_minutes=60)
        worker._transient_error = True

        next_run = worker.on_reschedule(payload)
        assert next_run.timestamp() == pytest.approx((utcnow() + datetime.timedelta(minutes=1)).timestamp())
        work_unit = payload.work_unit
        work_unit.refresh_from_db()
        assert work_unit.requirements.count() == 0
        assert work_unit.num_unsatisfied_requirements == 0

    def test_queue_process_changes(self):
        assert DumpDistributionData.objects.count() == 0
        assert ProcessChangelog.objects.count() == 0
        pc_work = queue_process_changes(serial_from=172, serial_to=731)
        assert isinstance(pc_work, ProcessChangelog)
        assert DumpDistributionData.objects.count() == 1
        assert ProcessChangelog.objects.count() == 1
        assert pc_work.serial_from == 172
        assert pc_work.serial_to == 731
        assert pc_work.num_distributions_added is None
        assert pc_work.num_distributions_removed is None
        assert pc_work.distributions_added.count() == 0
        assert pc_work.distributions_removed.count() == 0
        work_unit = pc_work.work_unit
        work_unit.refresh_from_db()
        assert work_unit.requirements.count() == 0
        assert work_unit.num_unsatisfied_requirements == 0
        ddd_work = DumpDistributionData.objects.first()
        assert ddd_work.serial_from == 172
        assert ddd_work.serial_to == 731
        assert ddd_work.shard == 0
        assert ddd_work.num_shards == 1
        assert ddd_work.bucket == "jambalaya"
        assert (
            ddd_work.key_prefix
            == "seinfeld/no-soup-for-you/data_dumps/python_distribution_data/172-731/python_distribution_data"
        )
        assert ddd_work.work_unit.requirements.count() == 1
        assert ddd_work.work_unit.num_unsatisfied_requirements == 1
        assert ddd_work.work_unit.requirements.first() == work_unit
