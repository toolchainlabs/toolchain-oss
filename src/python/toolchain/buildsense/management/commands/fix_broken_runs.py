# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
import zlib

from django.core.management.base import BaseCommand

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.buildsense.ingestion.models import ProcessPantsRun
from toolchain.buildsense.ingestion.run_info_raw_store import COMPRESSION_KEY, BuildFile, RunInfoRawStore, WriteMode
from toolchain.buildsense.ingestion.run_info_table import RunInfoTable
from toolchain.buildsense.ingestion.run_processors.python_coverage_xml import XmlCoverageArtifactsHandler
from toolchain.buildsense.records.run_info import RunInfo
from toolchain.workflow.models import WorkUnit

_logger = logging.getLogger(__name__)


class FixCoverageMetadata:
    def _is_compressed(self, content: bytes) -> bool:
        try:
            zlib.decompress(content)
        except zlib.error:
            return False
        else:
            return True

    def _re_upload_file(self, run_info: RunInfo, build_file: BuildFile) -> None:
        store = RunInfoRawStore.for_run_info(run_info)
        store.save_build_file(
            run_id=run_info.run_id,
            content_or_file=build_file.content,
            name=build_file.name,
            user_api_id=run_info.user_api_id,
            mode=WriteMode.OVERWRITE,
            dry_run=False,
            metadata=build_file.metadata,
            content_type="application/xml",
            is_compressed=True,
        )
        _logger.info(f"Fixed {build_file.name} for {run_info.run_id}")

    def maybe_fix(self, run_info: RunInfo) -> bool:
        store = RunInfoRawStore.for_run_info(run_info)
        build_file = store.get_named_data(run_info=run_info, name=XmlCoverageArtifactsHandler.types[0], optional=True)
        if not build_file or COMPRESSION_KEY in build_file.metadata:
            return False
        try:
            build_file.content.decode()
        except UnicodeDecodeError:
            if not self._is_compressed(build_file.content):
                return False
            self._re_upload_file(run_info, build_file)
            return True
        else:
            return False


class Command(BaseCommand):
    help = "Fix issues with pants runs data in the buildsense backend"
    _FIXERS = (FixCoverageMetadata,)

    def add_arguments(self, parser) -> None:
        parser.add_argument("--run-id", type=str, required=False, default=None, help="Pants Run ID.")
        parser.add_argument("--all", action="store_true", required=False, default=False, help="Process all infeasible.")

    def handle(self, *args, **options) -> None:
        run_id = options["run_id"]
        process_all = options["all"]
        if run_id and process_all:
            raise ToolchainAssertion("Must specify only one argument `--run-id` and `--all`")
        if run_id:
            self._process_single_run(run_id)
        elif process_all:
            self._process_all()
        else:
            raise ToolchainAssertion("Must specify `--run-id` or `--all`")

    def _process_single_run(self, run_id: str) -> None:
        ppr = ProcessPantsRun.objects.get(run_id=run_id)
        fixed = self.fix_pants_run(ppr)
        _logger.info(f"{run_id=} {fixed=}")
        if fixed:
            ppr.work_unit.mark_as_feasible()

    def _process_all(self) -> None:
        fixed_work_unit_ids = set()
        ct = WorkUnit.get_content_type_for_payload(ProcessPantsRun)
        qs = WorkUnit.get_by_state(ct, WorkUnit.INFEASIBLE)
        for wu in qs:
            if self.fix_pants_run(wu.payload):
                fixed_work_unit_ids.add(wu.id)
        _logger.info(f"proccessed {qs.count()} work units, fixed: {len(fixed_work_unit_ids)}")
        WorkUnit.mark_as_feasible_for_ids(fixed_work_unit_ids)

    def fix_pants_run(self, ppr: ProcessPantsRun) -> bool:
        table = RunInfoTable.for_customer_id(ppr.customer_id)
        run_info = table.get_by_run_id(repo_id=ppr.repo_id, user_api_id=ppr.user_api_id, run_id=ppr.run_id)
        if not run_info:
            raise ToolchainAssertion(f"Can't load {ppr.run_id} from DynamoDB.")
        return any(fixer().maybe_fix(run_info) for fixer in self._FIXERS)
