# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.crawler.base.crawler_worker_base import CrawlerWorkerBase
from toolchain.crawler.maven.maven_schedule_util import MavenScheduleUtil
from toolchain.crawler.maven.models import BINARY, SOURCE, IndexLatestVersionOfMavenArtifact, IndexMavenArtifact
from toolchain.django.webresource.models import WebResource
from toolchain.packagerepo.maven.artifact_locator import ArtifactLocator


class LatestMavenArtifactIndexer(CrawlerWorkerBase):
    """Schedules indexing of the latest version of a maven artifact."""

    schedule_util_cls = MavenScheduleUtil
    work_unit_payload_cls = IndexLatestVersionOfMavenArtifact

    def do_work(self, work_unit_payload):
        return work_unit_payload.artifact.latest_version() is not None

    def _jar_exists(self, coordinates, kind):
        jar_url_func = {SOURCE: ArtifactLocator.source_jar_url, BINARY: ArtifactLocator.binary_jar_url}
        return WebResource.resource_exists(jar_url_func[kind](coordinates))

    def on_success(self, work_unit_payload):
        latest = work_unit_payload.artifact.latest_version()
        kind = work_unit_payload.kind
        if self._jar_exists(latest.coordinates(), kind):
            IndexMavenArtifact.objects.get_or_create(
                artifact=latest.artifact, version=latest.version, corpus=str(latest.coordinates()), kind=kind
            )

    def on_reschedule(self, work_unit_payload):
        url = ArtifactLocator.maven_metadata_url(work_unit_payload.artifact)
        self.schedule_util.set_requirement(
            work_unit_payload, self.schedule_util.schedule_maven_metadata_processing(url)
        )
