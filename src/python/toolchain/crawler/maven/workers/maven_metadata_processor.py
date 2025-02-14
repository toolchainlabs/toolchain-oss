# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.crawler.maven.models import ProcessMavenMetadata
from toolchain.crawler.maven.workers.xml_resource_processor import XMLResourceProcessor
from toolchain.packagerepo.maven.models import (
    MavenArtifact,
    MavenArtifactVersion,
    MavenMetadata,
    MavenMetadataVersion,
    MavenStats,
)


class MavenMetadataProcessor(XMLResourceProcessor):
    """Processes maven-metadata.xml files."""

    work_unit_payload_cls = ProcessMavenMetadata

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._coordinates = None  # GACoordinates instance for an artifact.
        self._versions = []  # List of known versions of the artifact at self._coordinates.

    def process_xml(self):
        self._coordinates = self.ga_coordinates_from_xml(".")
        self._versions = self.text_list("versioning/versions/version")
        return True

    def on_success(self, work_unit_payload):
        artifact = MavenArtifact.for_coordinates(self._coordinates)
        maven_metadata = MavenMetadata.objects.get_or_create(web_resource=work_unit_payload.web_resource)[0]
        for version in self._versions:
            artifact_version = MavenArtifactVersion.objects.get_or_create(artifact=artifact, version=version)[0]
            MavenMetadataVersion.objects.get_or_create(maven_metadata=maven_metadata, artifact_version=artifact_version)

        # This code os buggy/not working. but now it causes lint issues.
        # So commenting it out, if/when we need it this can be enabled and fixed.
        # Schedule processing of each version's POM.
        # for version in self._versions:
        #     url = ArtifactLocator.pom_url(self._coordinates, version)
        #     self.schedule_util.schedule_extract_pom_info(url=url)

        # Update stats.
        if self._versions:
            # This is a metadata file representing an artifact (there are other maven-metadata.xml files,
            # e.e., those listing plugins)
            MavenStats.increment(
                f"{self._coordinates.group_id}:{self._coordinates.artifact_id}",
                num_artifacts=1,
                num_versions=len(self._versions),
            )
