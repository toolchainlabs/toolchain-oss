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
    help = (
        "Mark infeasible work as feasible, so it gets retried. Only operates on work with no unsatisfied "
        "requirements. Best called when no workers are running, so that this command doesn't get stuck re-marking "
        "the same work as feasible over and over again."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--payload-type", default=None, required=True, help="Act on work with payload of this type."
        )

    def handle(self, *args, **options):
        payload_type = transaction.content_type_mgr.filter(model=options["payload_type"].lower()).get().model_class()
        WorkUnit.mark_all_as_feasible(payload_type)
