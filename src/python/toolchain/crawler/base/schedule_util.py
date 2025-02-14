# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

from toolchain.crawler.base.models import FetchURL
from toolchain.django.webresource.models import WebResource
from toolchain.workflow.models import WorkUnit, WorkUnitPayload
from toolchain.workflow.work_context import get_calling_context

logger = logging.getLogger(__name__)


class ScheduleUtil:
    """Helper class to schedule various types of work.

    Also schedules any requirements that are known in advance. Note that this is just an optimization: The workers
    should be written to notice if any requirements aren't met, and reschedule themselves accordingly.

    Specific crawlers can subclass this to add more scheduling functions.
    """

    @staticmethod
    def schedule_fetch(url: str) -> FetchURL:
        """Helper function to schedule fetching of a url."""
        return FetchURL.get_or_create(url=url)

    @staticmethod
    def schedule_fetches(urls: list[str], batch_size: int = 1000) -> list[FetchURL]:
        """Helper function to schedule fetching of multiple urls."""
        return FetchURL.objects.bulk_create([FetchURL(url=url) for url in urls], batch_size=batch_size)

    @staticmethod
    def set_requirement(source: WorkUnitPayload, target: WorkUnitPayload) -> None:
        """Helper function to set a requirement of a source work unit payload on some target work unit payload."""
        created = source.add_requirement_by_id(target.work_unit_id)
        if created:
            logger.debug(f"Setting requirement: {source} -> {target}")
        else:
            logger.debug(f"Requirement already exists: {source} -> {target}")

    @staticmethod
    def schedule_webresource_work(work_unit_payload_cls: type[FetchURL], web_resource: WebResource) -> WorkUnit:
        """Helper function to schedule WebResource-related work of a certain type.

        :param work_unit_payload_cls: The type of work (a subclass of WebResourceWork).
        :param web_resource: Work on this WebResource.
        :return: An instance of work_unit_payload_cls.
        """
        work_unit, created = work_unit_payload_cls.objects.get_or_create(web_resource=web_resource)
        if logger.isEnabledFor(logging.INFO):
            # The worker class that called this function, not to be confused with the worker that will perform work_unit.
            scheduling_worker_cls, _ = get_calling_context()
            scheduling_worker_str = scheduling_worker_cls.__name__ if scheduling_worker_cls else "Unknown worker"
            if created:
                logger.debug(f"{scheduling_worker_str} scheduling work: {work_unit}")
            else:
                logger.debug(f"{scheduling_worker_str} skipping scheduling work. Work already exists: {work_unit}")
        return work_unit
