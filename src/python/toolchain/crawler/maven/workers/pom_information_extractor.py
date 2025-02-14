# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.conf import settings

from toolchain.base.datetime_tools import utcnow
from toolchain.crawler.maven.models import ExtractPOMInfo
from toolchain.crawler.maven.workers.pom_processor import POMProcessor
from toolchain.packagerepo.maven.artifact_locator import ArtifactLocator
from toolchain.packagerepo.maven.coordinates import GACoordinates
from toolchain.packagerepo.maven.models import (
    POM,
    License,
    MavenArtifact,
    MavenArtifactVersion,
    MavenDependency,
    Organization,
    POMArtifactVersion,
)
from toolchain.workflow.error import PermanentWorkException


class POMInfoExtractor(POMProcessor):
    """Extracts dependencies and other useful information from a POM file."""

    work_unit_payload_cls = ExtractPOMInfo

    class Error(PermanentWorkException):
        def __init__(self, pom_url, msg):
            super().__init__(f"while resolving {pom_url}: {msg}")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pom = None  # POM instance for the POM we're operating on.
        self._coordinates = None  # GAVCoordinates instance for the versioned artifact described in the POM.
        self._url = None  # URL of the project that produced the artifact described in the POM.
        self._scm_url = (
            None  # URL of the SCM containing the code from which the artifact described in the POM was built.
        )
        self._packaging = None  # Packaging for the artifact described in the POM (e.g., jar).
        self._organization_kwargs = None  # kwargs for an Organization instance.
        self._licenses_kwargs_list = []  # A list of kwargs for License instances.
        self._dependencies = {}  # Map from GACoordinates of a depended-on artifact to attrs of the dependency.

    def create_document_element(self):
        try:
            self._pom = self.web_resource.pom
        except POM.DoesNotExist:
            # Cause on_reschedule to add a requirement on the parent POM fetch.
            # Note that, currently, extraction work units are made to require the POM fetch at the
            # time they are created, as an optimization, so we won't hit this case in practice.
            # But there should be no hard requirement to do that, so we handle this case gracefully.
            return None
        return self.get_xml_chain(self._pom)

    def process_pom(self):
        self._coordinates = self.get_gav_coordinates()
        self._url = self.text("./url")
        self._scm_url = self.text("./scm/url")
        self._packaging = self.text("./packaging")
        self._organization_kwargs = self.child_text_map("./organization", ["name", "url"])
        self._licenses_kwargs_list = self.child_text_maps("./licenses/license", ["name", "url", "distribution"])

        deps = self.child_text_maps(
            "./dependencies/dependency", ["groupId", "artifactId", "version", "classifier", "type", "scope", "optional"]
        )
        for dep in deps:
            self._dependencies[GACoordinates(dep["groupId"], dep["artifactId"])] = {
                "depends_on_version_spec": dep["version"],
                "classifier": dep["classifier"],
                "type": dep["type"],
                "scope": dep["scope"],
                "optional": self._bool_from_text(dep["optional"]),
            }
        return True

    def on_success(self, work_unit_payload):
        artifact_version = MavenArtifactVersion.for_coordinates(self._coordinates)
        artifact_version.url = self._url
        artifact_version.scm_url = self._scm_url
        artifact_version.packaging = self._packaging
        if self._organization_kwargs is not None:
            artifact_version.organization, _ = Organization.objects.get_or_create(**self._organization_kwargs)
        artifact_version.licenses = [
            License.objects.get_or_create(**kwargs)[0] for kwargs in self._licenses_kwargs_list
        ]
        artifact_version.completed_at = utcnow()
        artifact_version.save()

        # Schedule fetch and process the link page for this pom's directory. It'll contain
        # links to the actual artifacts (jar files etc.)
        self.schedule_util.schedule_link_page_processing(ArtifactLocator.parent_link_page_url(work_unit_payload.url))

        POMArtifactVersion.objects.get_or_create(pom=self._pom, artifact_version=artifact_version)

        # Remove any old dep information.
        MavenDependency.objects.filter(dependent=artifact_version).delete()

        # We handle the deps in coordinate order.  This is to prevent deadlocks, in the
        # case where proc1 creates MavenArtifact_A and then MavenArtifact_B, while proc2
        # concurrently creates MavenArtifact_B and then attempts to create MavenArtifact_A.
        for depends_on_coords in sorted(self._dependencies.keys()):
            # Insert the dep.
            dep_properties = self._dependencies[depends_on_coords]
            depends_on = MavenArtifact.for_coordinates(depends_on_coords)
            maven_dep = MavenDependency(dependent=artifact_version, depends_on_artifact=depends_on, **dep_properties)
            maven_dep.save()
            if settings.FOLLOW_POM_DEPENDENCIES:
                # Schedule a fetch for the dependency's metadata.
                self.schedule_util.schedule_maven_metadata_processing(
                    ArtifactLocator.maven_metadata_url(depends_on_coords)
                )

    @staticmethod
    def _bool_from_text(text):
        """Convert a true/false string to a boolean.

        Quite permissive: Will recognize "true" in any capitalization as True, anything else as False.
        """
        return text.lower() == "true" if text else False

    def on_reschedule(self, work_unit_payload):
        if self.web_resource:
            # The superclass completed its part of do_work successfully, so we're the ones that returned
            # False from do_work() [via returning None from create_document_element()].
            # This indicates that the parent POM hasn't been fetched, so now ensure we depend on that.
            parent_pom_fetch = self.schedule_util.schedule_parent_pom_fetch(work_unit_payload.url)
            self.schedule_util.set_requirement(work_unit_payload, parent_pom_fetch)
        else:
            # The superclass was the one that returned False from do_work(), so let it handle the rescheduling.
            super().on_reschedule(work_unit_payload)
