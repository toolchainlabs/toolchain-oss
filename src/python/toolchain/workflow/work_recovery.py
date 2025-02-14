# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
import time

from django.db.models import Q

from toolchain.base.datetime_tools import utcnow
from toolchain.django.db.transaction_broker import TransactionBroker
from toolchain.workflow.config import WorkflowMaintenanceConfig
from toolchain.workflow.models import WorkUnit

logger = logging.getLogger(__name__)


transaction = TransactionBroker("workflow")


class WorkRecoverer:
    @classmethod
    def run_recover_forever(cls, config: WorkflowMaintenanceConfig) -> None:
        sleep_secs = config.recovery_sleep.total_seconds()
        batch_size = config.recovery_batch_size
        logger.info(f"WorkRecoverer.run_recover_forever sleep_secs={sleep_secs} batch_size={batch_size}")
        while True:
            logger.debug(f"WorkRecoverer going to sleep for {sleep_secs} seconds.")
            time.sleep(sleep_secs)
            ret = cls.recover_expired_work(batch_size)
            if ret:
                logger.info(f"WorkRecoverer recovered {ret} work units.")

    @classmethod
    def recover_expired_work(cls, batch_size: int):
        """Recovered expired work units.

        :return: the number of work units recovered.
        """
        with transaction.atomic():
            qs = cls._recovery_queryset(batch_size)
            n = 0
            for work_unit in qs:
                logger.info(f"Recovering expired work {work_unit}.")
                work_unit.revoke_lease()
                n += 1
            return n

    @classmethod
    def _recovery_queryset(cls, batch_size: int):
        now = utcnow()
        # First find some work units to recover.
        expired_workunit_pks_qs = WorkUnit.objects.filter(
            Q(leased_until__lt=now) | Q(leased_until__isnull=True), state=WorkUnit.LEASED
        ).values_list("pk", flat=True)[0:batch_size]
        # Now lock them, in id order (to prevent deadlocks). Note that we order here so that we
        # order after limit, instead of limit after order, which would have much worse performance.
        # We skip any rows that are already locked for whatever reason.
        qs = WorkUnit.objects.filter(pk__in=expired_workunit_pks_qs).order_by("pk").select_for_update(skip_locked=True)
        return qs
