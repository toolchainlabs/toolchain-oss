# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import hashlib
from collections import defaultdict

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.crawler.pypi.models import ProcessAllProjects, ProcessAllProjectsShard, ProcessProject
from toolchain.crawler.pypi.xmlrpc_api import AllProjects, ApiClient
from toolchain.workflow.worker import Worker


class AllProjectsProcessor(Worker):
    work_unit_payload_cls = ProcessAllProjects
    DEFAULT_LEASE_SECS = 15 * 60

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._all_projects: AllProjects | None = None

    def do_work(self, work_unit_payload: ProcessAllProjects) -> bool:
        if work_unit_payload.work_unit.requirements.exists():
            # We have scheduled our requirements, and they've succeeded, so we can now succeed.
            return True
        # We've not scheduled our requirements yet, so do so.
        # We schedule for all shards, so that each shard doesn't have to call ApiClient().get_all_projects()
        # separately, and discard most of the results.
        self._all_projects = ApiClient().get_all_projects()
        return False  # Reschedule ourselves.

    def on_reschedule(  # pylint: disable=useless-return
        self, work_unit_payload: ProcessAllProjects
    ) -> datetime.datetime | None:
        shards = [
            ProcessAllProjectsShard(process_all_projects=work_unit_payload, shard_number=shard_number)
            for shard_number in range(0, work_unit_payload.num_shards)
        ]
        work_unit_payload.work_unit.create_requirements(shards)
        process_project_work = defaultdict(list)
        if self._all_projects is None:
            raise ToolchainAssertion("self._all_projects is None")

        for project_name, latest_serial in self._all_projects.items():
            shard_number = (
                int.from_bytes(hashlib.sha256(project_name.encode()).digest(), byteorder="big")
                % work_unit_payload.num_shards
            )
            process_project_work[shard_number].append(
                ProcessProject(project_name=project_name, required_serial=latest_serial)
            )

        for shard_number, payloads in process_project_work.items():
            shards[shard_number].work_unit.create_requirements(payloads)

        return None
