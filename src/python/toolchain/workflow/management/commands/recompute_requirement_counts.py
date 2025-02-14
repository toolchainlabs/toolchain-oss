# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging

from django.core.management.base import BaseCommand

from toolchain.django.db.transaction_broker import TransactionBroker
from toolchain.workflow.models import WorkUnit

logger = logging.getLogger(__name__)


transaction = TransactionBroker("workflow")


# Reminder that Django requires this class to be named 'Command'.
# The command name is the module name.
class Command(BaseCommand):
    help = "Recompute requirement counts for pending work."

    def handle(self, *args, **options):
        num_checked = 0
        num_changed = 0
        num_transitioned_to_ready = 0
        done = False
        while not done:
            with transaction.atomic():
                # TODO: This isn't really going to cover all PENDING work units, since some will be transitioned to
                # READY by this command, so the paging by num_checked will be off.
                qs = WorkUnit.objects.filter(state=WorkUnit.PENDING).select_for_update()[
                    num_checked : num_checked + 10000
                ]
                p = num_checked
                for work_unit in qs:
                    num_checked += 1
                    actual_num_unsatisfied_reqs = work_unit.check_num_unsatisfied_requirements()
                    if actual_num_unsatisfied_reqs is not None:
                        num_changed += 1
                        if actual_num_unsatisfied_reqs == 0:
                            num_transitioned_to_ready += 1
                    if num_checked % 100 == 0:
                        print(
                            f"Checked {num_checked} work units: {num_changed} fixed and {num_transitioned_to_ready} transitioned to READY."
                        )
            if num_checked == p:
                done = True
