# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from prometheus_client import Gauge

from toolchain.base.datetime_tools import utcnow
from toolchain.crawler.base.models import FetchURL
from toolchain.crawler.pypi.exceptions import NoProjectData, StaleResponse, TransientError
from toolchain.crawler.pypi.json_api import get_project_data, purge
from toolchain.crawler.pypi.models import ProcessChangelog, ProcessDistribution
from toolchain.crawler.pypi.xmlrpc_api import ApiClient, ChangeLogEntry
from toolchain.lang.python.distributions.distribution_type import DistributionType, UnsupportedDistributionType
from toolchain.packagerepo.pypi.models import Distribution, InvalidDistError, Project, Release
from toolchain.workflow.error import AdvisoryWorkException
from toolchain.workflow.models import WorkUnit
from toolchain.workflow.worker import Worker

_logger = logging.getLogger(__name__)

CHANGED_PACKAGES = Gauge(
    name="toolchain_pypi_crawler_changed_packages",
    documentation="Number of changed packages we observe when crawlying pypi",
    labelnames=["change_type"],
    multiprocess_mode="all",
)


AddedDists = list[tuple[ChangeLogEntry, dict]]
RemovedDists = list[tuple[str, int]]


class ChangelogProcessor(Worker):
    DEFAULT_LEASE_SECS = 15 * 60
    work_unit_payload_cls = ProcessChangelog

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._added_dist_dicts: AddedDists = []  # List of (ChangeLogEntry, dist_dict).
        self._removed_files: RemovedDists = []  # List of (filename, serial).
        self._stale_projects: list[str] = []  # List of project names.
        self._retry_interval: timedelta | None = None

    def lease_secs(self, work_unit: WorkUnit) -> float:
        work_unit_payload: ProcessChangelog = work_unit.payload
        change_count = work_unit_payload.serial_to - work_unit_payload.serial_from
        return self.DEFAULT_LEASE_SECS + change_count

    def do_work(self, work_unit_payload: ProcessChangelog) -> bool:
        if (
            work_unit_payload.num_distributions_added is not None
            and work_unit_payload.num_distributions_removed is not None
        ):
            return True
        client = ApiClient()
        try:
            change_log = client.get_changed_packages(work_unit_payload.serial_from, work_unit_payload.serial_to)
        except TransientError:
            # Pypi outage, backoff & let it recover.
            self._retry_interval = timedelta(minutes=15)
            return False

        CHANGED_PACKAGES.labels(change_type="added").set(len(change_log.added))
        CHANGED_PACKAGES.labels(change_type="removed").set(len(change_log.removed))
        for entry in change_log.added:
            release_data = None
            try:
                project_data = get_project_data(entry.project, work_unit_payload.serial_from)
                release_data = project_data.get(entry.version)
            except NoProjectData:
                # Distribution, release or entire project data may be missing from the JSON API (e.g., if they were
                # deleted between the serial_from and now) so we don't fail on that.
                pass
            except TransientError as error:
                # Pypi outage, backoff & let it recover.
                self._retry_interval = timedelta(minutes=10)
                _logger.warning(f"transient error getting project data: {entry.project} {error!r}")
                return False
            except StaleResponse as error:
                # We got a stale cached response from the JSON API.
                purge(entry.project)
                self._stale_projects.append(entry.project)
                _logger.info(f"Stale project: {entry.project} {error!r}")
                self._retry_interval = timedelta(minutes=5)
                return False
            dist_dict = self._process_release(release_data, entry.filename)
            if dist_dict:
                self._added_dist_dicts.append((entry, dist_dict))

        self._removed_files.extend((entry.filename, entry.serial) for entry in change_log.removed)
        _logger.info(
            f"changed_packages serial_from={work_unit_payload.serial_from} serial_to={work_unit_payload.serial_to} {change_log} stale={len(self._stale_projects)} add_dists={len(self._added_dist_dicts)}"
        )
        return False

    def _process_release(self, release_data: list[dict[str, Any]] | None, filename: str) -> dict | None:
        if not release_data:
            return None
        for dist in release_data:
            if dist.get("filename") != filename:
                continue
            try:
                dist_type = DistributionType.from_setuptools_packagetype(dist["packagetype"])
            except UnsupportedDistributionType as ex:
                raise AdvisoryWorkException(str(ex))
            dist["dist_type"] = dist_type.value
            return dist
        return None

    @classmethod
    def _process_added(cls, work_unit_payload: ProcessChangelog, added_dist_dicts: AddedDists) -> list[Distribution]:
        added_dists = []
        _logger.info(f"Distributions to process {len(added_dist_dicts)}")
        for changelog_entry, dist_dict in added_dist_dicts:
            try:
                dist = cls._add_dist(changelog_entry, dist_dict)
            except InvalidDistError as error:
                _logger.warning(f"Skip invalid distribution: {changelog_entry=} {error!r}")
                continue
            added_dists.append(dist)
            if dist.dist_type in ProcessDistribution.processable_dist_types:
                pd = ProcessDistribution.get_or_create(distribution=dist)
                pd.add_requirement_by_id(FetchURL.get_or_create(dist.url).work_unit_id)
                work_unit_payload.add_requirement_by_id(pd.work_unit_id)
        return added_dists

    @classmethod
    def _add_dist(cls, changelog_entry: ChangeLogEntry, dist_dict: dict):
        project = Project.get_or_create(changelog_entry.project)
        release = Release.get_or_create(project, changelog_entry.version)
        dist = Distribution.get_or_create_from_dict(dist_dict, release, serial_from=changelog_entry.serial)
        return dist

    @staticmethod
    def _process_removed(removed_files: RemovedDists) -> list[Distribution]:
        removed_dists = []
        if removed_files:
            _logger.info(f"Removing {len(removed_files)} distributions")
        # TODO: we can probably batch those DB calls.
        for filename, serial in removed_files:
            dist = Distribution.get_or_none(filename=filename)
            if not dist:
                continue
            dist.serial_to = serial
            dist.save()
            removed_dists.append(dist)
        return removed_dists

    def on_reschedule(self, work_unit_payload: ProcessChangelog) -> datetime | None:
        if self._retry_interval:
            return utcnow() + self._retry_interval
        added_dists = self._process_added(work_unit_payload, self._added_dist_dicts)
        removed_dists = self._process_removed(self._removed_files)
        work_unit_payload.update_processed_dists(added=added_dists, removed=removed_dists)
        return None
