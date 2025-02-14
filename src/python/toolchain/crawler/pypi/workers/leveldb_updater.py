# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging

from toolchain.aws.errors import is_transient_aws_error
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.crawler.pypi.models import UpdateLevelDb
from toolchain.lang.python.modules.module_distribution_map_builder import DistributionModuleMapBuilder
from toolchain.satresolver.pypi.depgraph_builder import DepgraphBuilder
from toolchain.util.file.create import create_directory, create_file
from toolchain.util.leveldb.builder import Builder
from toolchain.util.leveldb.urls import input_list_for_leveldb
from toolchain.workflow.constants import WorkExceptionCategory
from toolchain.workflow.models import WorkUnit
from toolchain.workflow.worker import Worker

logger = logging.getLogger(__name__)


class LevelDbUpdater(Worker):
    _FULL_BUILD_LEASE = datetime.timedelta(hours=5)
    _INCREMENTAL_BUILD_LEASE = datetime.timedelta(minutes=40)
    work_unit_payload_cls = UpdateLevelDb

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._input_file_urls = None

    def classify_error(self, exception: Exception) -> WorkExceptionCategory | None:
        if is_transient_aws_error(exception):
            return WorkExceptionCategory.TRANSIENT
        return None

    def transient_error_retry_delay(
        self, work_unit_payload: UpdateLevelDb, exception: Exception
    ) -> datetime.timedelta | None:
        # Crawl is not time critical, so it is better to back of for a few minutes and let things recover.
        return datetime.timedelta(minutes=8)

    def lease_secs(self, work_unit: WorkUnit) -> float:
        full_build = not bool(work_unit.payload.existing_leveldb_dir_url)
        lease_time = self._FULL_BUILD_LEASE if full_build else self._INCREMENTAL_BUILD_LEASE
        return lease_time.total_seconds()

    def do_work(self, work_unit_payload: UpdateLevelDb) -> bool:
        input_dir = create_directory(work_unit_payload.input_dir_url)
        available_input_file_urls = {input_file.url() for input_file in input_dir.list()}

        existing_input_file_urls = set()
        if work_unit_payload.existing_leveldb_dir_url:
            existing_input_list_file = create_file(input_list_for_leveldb(work_unit_payload.existing_leveldb_dir_url))
            if existing_input_list_file.exists():
                existing_input_file_urls.update(
                    existing_input_list_file.get_content().decode().splitlines(keepends=False)
                )

        new_input_file_urls = available_input_file_urls.difference(existing_input_file_urls)
        logger.info(
            f"LevelDbUpdater {input_dir=} num_files={len(available_input_file_urls)} num_new_files={len(new_input_file_urls)}"
        )

        if not new_input_file_urls:
            return True
        builder = self._get_builder_cls(work_unit_payload)(
            input_urls=tuple(new_input_file_urls),
            output_dir_url=work_unit_payload.output_dir_url,
            existing_leveldb_dir_url=work_unit_payload.existing_leveldb_dir_url,
        )
        builder.run()

        # Writing the input list file, which is an atomic operation, signifies that the leveldb is valid.
        # Code should not attempt to read the leveldb unless its input list file is present.
        new_file_url = input_list_for_leveldb(work_unit_payload.output_dir_url)
        new_input_list_file = create_file(new_file_url)
        new_input_list_file.set_content("\n".join(sorted(available_input_file_urls)).encode())
        logger.info(f"LevelDbUpdater write: {new_file_url=} urls={len(available_input_file_urls)}")
        return True

    def _get_builder_cls(self, work_unit_payload: UpdateLevelDb) -> type[Builder]:
        if work_unit_payload.builder_cls == "DepgraphBuilder":
            return DepgraphBuilder
        elif work_unit_payload.builder_cls == "DistributionModuleMapBuilder":
            return DistributionModuleMapBuilder
        else:
            raise ToolchainAssertion(f"Unknown builder class {work_unit_payload.builder_cls}")
