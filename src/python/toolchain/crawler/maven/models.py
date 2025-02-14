# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.db.models import CASCADE, CharField, ForeignKey
from django.urls import reverse

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.crawler.base.models import KytheEntriesBase, WebResourceWork
from toolchain.packagerepo.maven.coordinates import GAVCoordinates
from toolchain.packagerepo.maven.models import MavenArtifact, MavenArtifactVersion
from toolchain.workflow.models import WorkUnitPayload

SOURCE = "SRC"
BINARY = "BIN"

INDEX_KINDS = {SOURCE: "lib", BINARY: "lib-binary-jar"}


class MavenArtifactKytheEntries(KytheEntriesBase):
    """Kythe entries indexed from a maven artifact.

    Note that we don't extend HasGAVCoordinates because we must extend KytheEntriesBase, and we don't want to add
    multiple inheritance complexity to the already complex metaclass tangle of django Model. Also, our uniqueness
    constraints are different.
    """

    class Meta:
        unique_together = ("artifact", "version", "kind")

    artifact = ForeignKey(MavenArtifact, on_delete=CASCADE)

    version = CharField(max_length=150)

    kind = CharField(max_length=3, choices=sorted(INDEX_KINDS.items()))

    @classmethod
    def for_coordinates(cls, coordinates):
        """Return a list of instances identified by the given coordinates.

        There should be at most two entries in the returned list - one index entry for the source jar and one index entry
        for the binary jar.
        """
        try:
            return list(
                cls.objects.filter(artifact=MavenArtifact.for_coordinates(coordinates), version=coordinates.version)
            )
        except cls.DoesNotExist:
            return []

    @classmethod
    def for_coordinates_and_kind(cls, coordinates, kind):
        """Return an instance identified by the given coordinates and kind."""
        try:
            return cls.objects.get(
                artifact=MavenArtifact.for_coordinates(coordinates), version=coordinates.version, kind=kind
            )
        except cls.DoesNotExist:
            return None


class MavenWebResourceWork(WebResourceWork):
    """A base class for maven-related work units that are identified by a unique URL."""

    class Meta:
        abstract = True


class ProcessLinkPage(MavenWebResourceWork):
    """Process HTML pages containing links to other resources."""

    def get_absolute_url(self):
        return reverse("crawler:processlinkpage_detail", args=[self.pk])


class ProcessMavenMetadata(MavenWebResourceWork):
    """Process a maven-metadata.xml file."""

    def get_absolute_url(self):
        return reverse("crawler:processmavenmetadata_detail", args=[self.pk])


class LocateParentPOM(MavenWebResourceWork):
    """Locate a POM's parent POM (if any).

    This object's url field is that of the child POM whose parent we locate.
    """

    def get_absolute_url(self):
        return reverse("crawler:locateparentpom_detail", args=[self.pk])


class ExtractPOMInfo(MavenWebResourceWork):
    """Extract dependencies and other useful information from a POM file."""

    def get_absolute_url(self):
        return reverse("crawler:extractpominfo_detail", args=[self.pk])


class IndexLatestVersionOfMavenArtifact(WorkUnitPayload):
    """Index the latest version of a maven artifact.

    Will index either binary or source jar according to the value of kind.
    """

    artifact = ForeignKey(MavenArtifact, on_delete=CASCADE)

    kind = CharField(max_length=3, choices=sorted(INDEX_KINDS.items()))

    @classmethod
    def for_coordinates_and_kind(cls, coordinates, kind):
        artifact = MavenArtifact.for_coordinates(coordinates)
        return cls.objects.get_or_create(artifact=artifact, kind=kind)[0]

    @property
    def description(self):
        return f"{self.artifact.coordinates()} {self.kind.lower()}"

    def get_absolute_url(self):
        return reverse("crawler:indexlatestversionofmavenartifact_detail", args=[self.pk])


class IndexMavenArtifact(WorkUnitPayload):
    """Invoke the Kythe indexer on a Maven GAV artifact.

    Note that we don't extend HasGAVCoordinates because we must extend WorkUnitPayload, and we don't want to add
    multiple inheritance complexity to the already complex metaclass tangle of django Model. Also, our uniqueness
    constraints are different.
    """

    class Meta:
        unique_together = ("artifact", "version", "corpus", "kind")

    @classmethod
    def get_kind(cls, kind):
        if kind not in INDEX_KINDS:
            raise ToolchainAssertion(f"Unknown kind {kind}")
        return INDEX_KINDS[kind]

    artifact = ForeignKey(MavenArtifact, on_delete=CASCADE)

    version = CharField(max_length=150)

    # The corpus name to assign to the generated vnames.
    corpus = CharField(max_length=500)

    # Which target kind to operate over.
    kind = CharField(max_length=3, choices=sorted(INDEX_KINDS.items()))

    @classmethod
    def for_coordinates_and_kind(cls, coordinates, kind):
        """Return an instance identified by the given coordinates and kind."""
        try:
            return cls.objects.get(
                artifact__group_id=coordinates.group_id,
                artifact__artifact_id=coordinates.artifact_id,
                version=coordinates.version,
                kind=kind,
            )
        except cls.DoesNotExist:
            return None

    def maven_artifact_version(self):
        return MavenArtifactVersion.for_coordinates(self.coordinates())

    def coordinates(self):
        return GAVCoordinates(self.artifact.group_id, self.artifact.artifact_id, self.version)

    @property
    def description(self):
        return f"{self.coordinates()} {self.kind.lower()}"

    def get_absolute_url(self):
        return reverse("crawler:indexmavenartifact_detail", args=[self.pk])
