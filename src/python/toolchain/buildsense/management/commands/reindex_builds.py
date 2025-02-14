# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
import time
from collections.abc import Iterator

from dateutil.parser import parse
from django.conf import settings
from django.core.management.base import BaseCommand

from toolchain.buildsense.ingestion.run_info_table import RunInfoTable
from toolchain.buildsense.records.run_info import RunInfo
from toolchain.buildsense.search.run_info_index import RunInfoIndex
from toolchain.django.site.models import Customer, Repo

_logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Reindex Builds from DynamoDB to ES"
    _BATCH_SIZE = 100
    _INDEX_CLIENT_TTL = 120  # 2min

    def add_arguments(self, parser):
        parser.add_argument("--start-date", type=str, required=False, default=None, help="Start date.")
        parser.add_argument(
            "--throttle",
            type=str,
            required=False,
            default="30,2500",
            help="throttle interval & count (comma separated).",
        )

    def handle(self, *args, **options):
        throttle_internval, _, throttle_count = options["throttle"].partition(",")
        start_date_str = options["start_date"]
        start_date = (
            parse(start_date_str) if start_date_str else datetime.datetime(2019, 1, 1, tzinfo=datetime.timezone.utc)
        )
        self.reindex_builds(
            int(throttle_internval), int(throttle_count), start_date.replace(tzinfo=datetime.timezone.utc)
        )

    def reindex_builds(self, throttle_internval, throttle_count, earliest: datetime.datetime) -> int:
        total_builds = 0
        for customer in Customer.base_qs().all():
            for repo in Repo.for_customer_id(customer.id):
                count = self._index_repo_builds(repo, throttle_internval, throttle_count, earliest)
                total_builds += count
        return total_builds

    def _index_repo_builds(
        self, repo: Repo, throttle_internval: int, throttle_count: int, earliest: datetime.datetime
    ) -> int:
        start = time.time()
        table = RunInfoTable.for_customer_id(repo.customer_id)
        run_info_index = RunInfoIndex.for_customer_id(settings, repo.customer_id)
        repo_slug = f"{repo.customer.slug}/{repo.slug}"
        _logger.info(f"Index for repo: {repo_slug}")
        total_builds = 0
        for run_infos in self._iter_pages(table, repo, earliest):
            total_builds += len(run_infos)
            first, last = run_infos[0].timestamp, run_infos[-1].timestamp
            _logger.info(f"Index {len(run_infos)} for {repo_slug} total={total_builds} ({first} - {last})")
            run_info_index.index_runs(run_infos)
            if total_builds % throttle_count == 0:
                _logger.info(f"Throttle (sleep) for {throttle_internval} seconds")
                time.sleep(throttle_internval)
            if time.time() - start >= self._INDEX_CLIENT_TTL:
                run_info_index = RunInfoIndex.for_customer_id(settings, repo.customer_id)
                start = time.time()
        return total_builds

    def _iter_pages(
        self, table: RunInfoTable, repo: Repo, earliest: datetime.datetime
    ) -> Iterator[tuple[RunInfo, ...]]:
        cursor = None
        while True:
            result_page = table.get_repo_builds(
                repo_id=repo.id, earliest=earliest, cursor=cursor, limit=self._BATCH_SIZE
            )
            run_infos = result_page.results
            cursor = result_page.cursor
            if not run_infos:
                break
            yield run_infos
            if not result_page.cursor:
                break
