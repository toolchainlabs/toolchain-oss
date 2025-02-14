# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging

from django.core.management.base import BaseCommand
from rich.console import Console
from rich.table import Column, Table

from toolchain.base.datetime_tools import utcnow
from toolchain.buildsense.ingestion.run_info_table import RunInfoTable
from toolchain.buildsense.ingestion.run_processors.ci_annotations import CIAnnotationHelper, SourceErrorAnnotation
from toolchain.django.site.models import Repo

_logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run flake8 errors parser"

    def add_arguments(self, parser):
        parser.add_argument(
            "--repo", type=str, required=True, default="toolchainlabs/toolchain", help="customer/repo (slugs)."
        )

    def handle(self, *args, **options):
        customer_slug, _, repo_slug = options["repo"].partition("/")
        repo = Repo.get_for_slugs_or_none(customer_slug=customer_slug, repo_slug=repo_slug)
        helper = CIAnnotationHelper()
        table = RunInfoTable.for_customer_id(customer_id=repo.customer_id)
        for run_infos in table.iterate_repo_builds(
            repo_id=repo.id, earliest=datetime.datetime(2021, 1, 1, tzinfo=datetime.timezone.utc), latest=utcnow()
        ):
            for run_info in run_infos:
                print(".", flush=True, end="")
                if "lint" not in run_info.computed_goals:
                    continue
                if run_info.outcome != "FAILURE":
                    continue
                print("\n")
                annotations = helper.get_annotations(run_info)
                _logger.info(
                    f"Look at {run_info.run_id} goals={run_info.computed_goals} annotations={len(annotations)}"
                )
                self.print_annotations(annotations)

    def print_annotations(self, annotations: list[SourceErrorAnnotation]) -> None:
        if not annotations:
            return
        table = Table(
            Column(header="File", style="dim"),
            "position",
            "error",
            "message",
            show_header=True,
            header_style="bold magenta",
        )
        for ann in annotations[:10]:
            table.add_row(ann.file_path, f"{ann.lines[0]}:{ann.columns[0]}", ann.error_code, ann.message)

        Console().print(table)
