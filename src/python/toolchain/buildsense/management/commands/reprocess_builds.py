# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging

from django.core.management.base import BaseCommand

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.buildsense.ingestion.models import ProcessPantsRun
from toolchain.django.site.models import Repo
from toolchain.workflow.models import WorkUnit, transaction

_logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Rerun background processing on recent pants builds"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            required=False,
            default=14,
            help="Reprocess builds that occurred between now and this number of days in the past.",
        )
        parser.add_argument("--repo", type=str, required=False, default=None, help="customer/repo (slugs).")

    def handle(self, *args, **options):
        from_date = utcnow() - datetime.timedelta(days=options["days"])
        repo_fn = options["repo"]
        if not repo_fn:
            _logger.info(f"process build starting from date: {from_date}")
            WorkUnit.rerun_all(ProcessPantsRun, from_date=from_date)
            return
        customer_slug, _, repo_slug = repo_fn.partition("/")
        repo = Repo.get_for_slugs_or_none(customer_slug=customer_slug, repo_slug=repo_slug)
        if not repo:
            raise ToolchainAssertion(f"Repo {options['repo']} not found)")
        qs = ProcessPantsRun.objects.select_related("work_unit").filter(
            repo_id=repo.id,
            work_unit__created_at__gte=from_date,
            work_unit__state=WorkUnit.SUCCEEDED,
        )
        _logger.info(f"process build for {repo_fn} repo starting from date: {from_date}. {qs.count()} builds")
        with transaction.atomic():
            for ppr in qs:
                ppr.work_unit.rerun()
