# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.crawler.base.crawler_worker_base import CrawlerWorkerBase
from toolchain.workflow.models import WorkUnitPayload


class WebResourceProcessor(CrawlerWorkerBase):
    """Base class for workers that process a previously-fetched web resource."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._web_resource = None

    @property
    def web_resource(self):
        return self._web_resource

    def process(self) -> bool:
        """Subclasses implement this to process the web resource.

        Exceptions and return values are as documented for `toolchain.workflow.worker.Worker#do_work`.
        """
        raise NotImplementedError()

    def do_work(self, work_unit_payload) -> bool:
        self._web_resource = work_unit_payload.web_resource
        if self._web_resource is None:
            return False  # Reschedule to run after fetching.
        return self.process()

    def on_reschedule(self, work_unit_payload: WorkUnitPayload) -> None:
        self.schedule_util.set_requirement(work_unit_payload, self.schedule_util.schedule_fetch(work_unit_payload.url))
