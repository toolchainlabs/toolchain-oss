# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.crawler.pypi.models import ProcessAllProjectsShard
from toolchain.workflow.worker import Worker


class AllProjectsShardProcessor(Worker):
    work_unit_payload_cls = ProcessAllProjectsShard

    def do_work(self, work_unit_payload: ProcessAllProjectsShard) -> bool:
        # The ProcessAllProjectsShards exist just to shard contention on the global ProcessAllProjects instance.
        # The scheduling of all work in all shards is taken care of by AllProjectsProcessor,
        # so we don't need to do any of that, and we will only run at all if ProcessProject for
        # all projects in this shard succeeded, so we don't need to do anything at all here.
        return True
