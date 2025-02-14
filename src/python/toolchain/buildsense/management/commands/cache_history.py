# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
import re
import time

from dateutil.parser import parse
from django.core.management.base import BaseCommand

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.buildsense.build_data_queries import BuildsQueries
from toolchain.buildsense.ingestion.run_info_raw_store import RunInfoRawStore
from toolchain.django.site.models import Repo

_logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Display the cache history of a process (by description), to help debug cache misses.\n"
        "\n"
        "Renders all matches in descending time order, so it can be useful to pipe the output to `more` or `head`."
    )

    def add_arguments(self, parser):
        parser.add_argument("--customer", type=str, required=True, default=None, help="Customer slug to query.")
        parser.add_argument("--repo", type=str, required=True, default=None, help="Repo slug to query.")
        parser.add_argument("--branch", type=str, required=True, default=None, help="Branch name to query within.")
        parser.add_argument(
            "--description",
            type=str,
            required=True,
            default=None,
            help="Description of the process to regex match for.",
        )
        parser.add_argument("--start-date", type=str, required=False, default=None, help="Start date.")
        parser.add_argument(
            "--throttle",
            type=str,
            required=False,
            default="30,2500",
            help="throttle interval & count (comma separated).",
        )

    def handle(self, *args, **options):
        customer_slug = options["customer"]
        repo_slug = options["repo"]
        branch = options["branch"]
        description = re.compile(options["description"])
        throttle_interval, _, throttle_count = options["throttle"].partition(",")
        start_date_str = options["start_date"]
        start_date = (
            parse(start_date_str) if start_date_str else datetime.datetime(2021, 7, 1, tzinfo=datetime.timezone.utc)
        )

        repo = Repo.get_for_slugs_or_none(customer_slug=customer_slug, repo_slug=repo_slug)
        if not repo:
            raise ToolchainAssertion(f"No matching repo for customer {customer_slug} and repo: {repo_slug}")
        self.render_history(
            repo,
            branch,
            description,
            int(throttle_interval),
            int(throttle_count),
            start_date.replace(tzinfo=datetime.timezone.utc),
        )

    def render_history(
        self,
        repo: Repo,
        branch: str,
        description: re.Pattern,
        throttle_interval: int,
        throttle_count: int,
        earliest: datetime.datetime,
    ) -> None:
        index = BuildsQueries.for_customer_id(repo.customer_id)
        run_info_raw_store = RunInfoRawStore.for_repo(repo)
        page_idx = 0
        builds_since_throttled = 0
        total_pages: int | None = None
        while total_pages is None or page_idx < total_pages:
            page = index.search_all_matching(repo.id, {"branch": branch}, earliest=earliest, page=page_idx)
            if total_pages is None:
                total_pages = page.total_pages
            page_idx += 1
            for run_info in page.results:
                build_data = run_info_raw_store.get_build_data(run_info)
                self._maybe_render_matches(build_data, description)

            builds_since_throttled += len(page.results)
            if builds_since_throttled > throttle_count:
                _logger.info(f"Throttle (sleep) for {throttle_interval} seconds")
                time.sleep(throttle_interval)
                builds_since_throttled = 0

    def _maybe_render_matches(
        self,
        build_data: dict,
        description: re.Pattern,
    ) -> None:
        run_info = build_data["run_info"]
        run_id = run_info["id"]
        user = run_info.get("user", "")
        workunits = build_data.get("workunits", [])
        for workunit in workunits:
            workunit_description = workunit.get("description", "")
            if not description.search(workunit_description):
                continue

            # We've matched a process: render it.
            start_usecs = workunit.get("start_usecs")
            source = workunit.get("metadata", {}).get("source")
            definition = workunit.get("metadata", {}).get("definition")

            if start_usecs and source and definition:
                self._render_match(start_usecs, user, run_id, source, definition)
            else:
                _logger.debug(f"Matched workunit was missing one of: {start_usecs}, {source}, {definition}.")

    def _render_match(self, start_usecs: int, user: str, run_id: str, source: str, definition: str) -> None:
        print(f"{start_usecs}\t{user}\t{run_id}\t{source}\t{definition}")
