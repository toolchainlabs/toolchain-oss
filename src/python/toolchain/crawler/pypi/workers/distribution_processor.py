# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
import os

from toolchain.aws.errors import is_transient_aws_error
from toolchain.base.fileutil import temporary_dir
from toolchain.base.toolchain_error import ToolchainError
from toolchain.crawler.base.models import FetchURL
from toolchain.crawler.pypi.models import ProcessDistribution
from toolchain.django.webresource.models import WebResource
from toolchain.lang.python.distributions.distribution_metadata import extract_metadata
from toolchain.lang.python.distributions.distribution_reader import get_modules_for_dist
from toolchain.packagerepo.pypi.models import Distribution, DistributionData
from toolchain.workflow.constants import WorkExceptionCategory
from toolchain.workflow.error import AdvisoryWorkException
from toolchain.workflow.worker import Worker

_logger = logging.getLogger(__name__)


class DistributionProcessor(Worker):
    """Extract the metadata from a python distribution."""

    work_unit_payload_cls = ProcessDistribution

    def classify_error(self, exception: Exception) -> WorkExceptionCategory | None:
        if is_transient_aws_error(exception):
            return WorkExceptionCategory.TRANSIENT
        return None

    def transient_error_retry_delay(
        self, work_unit_payload: ProcessDistribution, exception: Exception
    ) -> datetime.timedelta | None:
        # Crawl is not time critical, so it is better to back of for a few minutes and let things recover.
        return datetime.timedelta(minutes=10)

    def _extract_metadata_and_modules(self, web_resource: WebResource, filename: str) -> tuple[dict, list[str]]:
        """Extracts the metadata from a python distribution."""
        # Note: pkginfo will parse the requirements correctly for the current system architecture.
        with temporary_dir() as tmpdir:
            dist_path = os.path.join(tmpdir, filename)
            web_resource.dump_content(dist_path)
            _logger.info(f"dist: {filename}, size: {os.stat(dist_path).st_size:,} bytes")
            try:
                distribution_type, metadata = extract_metadata(dist_path)
                modules = sorted(get_modules_for_dist(distribution_type, dist_path))
            except ToolchainError as ex:
                raise AdvisoryWorkException(str(ex))
        return metadata, modules

    def do_work(self, work_unit_payload: ProcessDistribution) -> bool:
        dist: Distribution = work_unit_payload.distribution
        web_resource = WebResource.latest_by_url(url=dist.url)
        if not web_resource:
            _logger.warning(f"failed to load WebResource for {dist} from url={dist.url}")
            return False

        # We shouldn't schedule unprocessable dists for processing, but check here in case we did.
        if dist.dist_type not in ProcessDistribution.processable_dist_types:
            _logger.warning(f"{dist}  type={dist.dist_type} is not supported")
            return True
        metadata, modules = self._extract_metadata_and_modules(web_resource, dist.filename)
        _logger.info(f"extracted metadata and {len(modules)} for dist: {dist.filename}")
        DistributionData.update_or_create(
            distribution=dist, web_resource=web_resource, metadata=metadata, modules=modules
        )
        return True

    def on_reschedule(  # pylint: disable=useless-return
        self, work_unit_payload: ProcessDistribution
    ) -> datetime.datetime | None:
        # If we get here it means there was no FetchURL work scheduled for our URL.
        # In practice we pre-schedule the FetchURL work along with scheduling the ProcessDistribution,
        # but it never hurts to be robust.
        fetch_url = FetchURL.get_or_create(url=work_unit_payload.distribution.url)
        work_unit_payload.add_requirement_by_id(fetch_url.work_unit_id)
        return None
