# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
import random

from django.contrib.postgres.fields import ArrayField
from django.db.models import (
    CASCADE,
    BooleanField,
    CharField,
    DateTimeField,
    F,
    ForeignKey,
    Func,
    IntegerField,
    ManyToManyField,
    Max,
    OneToOneField,
    Subquery,
    Sum,
    URLField,
    Value,
)
from django.db.models.functions import Cast
from django.urls import reverse

from toolchain.base.datetime_tools import UNIX_EPOCH
from toolchain.django.db.base_models import ToolchainModel
from toolchain.django.webresource.models import WebResource
from toolchain.packagerepo.maven.artifact_locator import ArtifactLocator
from toolchain.packagerepo.maven.coordinates import GACoordinates, GAVCoordinates
from toolchain.workflow.error import PermanentWorkException

logger = logging.getLogger(__name__)


def choice(ch):
    """A helper for creating model fields whose values are restricted to a set of choices.

    When defining such a field, Django requires each choice to be a pair of (database value, human- readable value for
    use in forms). This helper function is convenient when the human-readable value is the same as the database value.
    """
    return ch, ch


class License(ToolchainModel):
    """A software usage license.

    See https://maven.apache.org/pom.html#Licenses for details.
    """

    class Meta:
        unique_together = ("name", "url", "distribution")

    name = CharField(max_length=300, db_index=True, blank=True)

    url = URLField(max_length=500, db_index=True, blank=True)

    REPO = "repo"
    MANUAL = "manual"
    DISTRIBUTION_CHOICES = (choice(REPO), choice(MANUAL))

    distribution = CharField(max_length=20, choices=DISTRIBUTION_CHOICES, blank=True)

    def __str__(self):
        return f"{self.name} ({self.url})"


class Organization(ToolchainModel):
    """An organization that creates Maven artifacts.

    See https://maven.apache.org/pom.html#Organization for details.
    """

    class Meta:
        unique_together = ("name", "url")

    name = CharField(max_length=150, db_index=True, blank=True, default="")

    url = URLField(max_length=500, db_index=True, blank=True, default="")

    def __str__(self):
        return f"{self.name} ({self.url})" if self.url else self.name


# See https://maven.apache.org/pom.html#Maven_Coordinates for details on Maven artifact coordinates.


class MavenArtifact(ToolchainModel):
    """An unversioned Maven artifact."""

    class Meta:
        unique_together = ("group_id", "artifact_id")

    group_id = CharField(max_length=150)

    artifact_id = CharField(max_length=150)

    @classmethod
    def for_coordinates(cls, coordinates):
        return cls.objects.get_or_create(group_id=coordinates.group_id, artifact_id=coordinates.artifact_id)[0]

    def all_versions(self):
        """Returns all versions of this artifact, as a list of MavenArtifactVersion, in descending semver order."""
        sortable_version = self._get_sortable_version_expr()
        # Now use this as the sort key.
        qs = (
            MavenArtifactVersion.objects.filter(artifact=self)
            .annotate(sortable_version=sortable_version)
            .order_by(F("sortable_version").desc())
        )
        return list(qs)

    def latest_version(self):
        """Returns the latest known version of this artifact, as a MavenArtifactVersion.

        Returns None if there are no known versions of this artifact.
        """
        # We carefully construct a single query that will return the instance with the maximal version.
        sortable_version = self._get_sortable_version_expr()

        # First, construct a queryset that returns the max sortable_version.
        # Note that aggregate() is a terminal clause for a QuerySet that returns a dictionary of name-value pairs,
        # not a queryset, so we can't use it as a subquery. Instead we use a neat trick to get Django to
        # create an aggregate queryset without grouping.
        # This works by grouping the annotation by the constant 1, which every row will group into.
        # We then strip this grouping column from the select list (the second values()).
        # Django (now) knows enough to determine that the grouping is redundant, and eliminates it.
        # Leaving a single query with the exact SQL we needed.
        # See https://stackoverflow.com/questions/9838264/django-record-with-max-element.
        max_sortable_version_qs = (
            MavenArtifactVersion.objects.filter(artifact=self)
            .annotate(common=Value(1))
            .values("common")
            .annotate(max_sortable_version=Max(sortable_version))
            .values("max_sortable_version")
        )

        # Now, use that queryset as a subquery to fetch the actual MavenArtifactVersion instance.
        # It's theoretically possible to have multiple instances with the same sortable_version, since
        # we strip out all non-numeric characters to create the sortable_version. So we explicitly restrict
        # to just one result.
        qs = MavenArtifactVersion.objects.annotate(sortable_version=sortable_version).filter(
            artifact=self, sortable_version=Subquery(max_sortable_version_qs)
        )[0:1]
        res = list(qs)
        return res[0] if res else None

    @staticmethod
    def _get_sortable_version_expr():
        """Returns a Django DB expression, on a string 'version' field, whose values have semver order.

        E.g., '1.2' -> (1, 2); '1.20.2' -> (1, 20, 2); '4.12-beta-1' -> (4, 12, 1).
        """
        # We split the version on any non-numeric characters, which lets us deal with things like '4.12-beta-1'.
        split_version = Func(F("version"), Value("[^0-9]+"), function="regexp_split_to_array")
        # Then we strip any empty strings out of the array (e.g., the array will end in an empty string
        # if the last character in the version was non-numeric).
        stripped_split_version = Func(split_version, Value(""), function="array_remove")
        # We cast the result to an array of ints (which is a valid cast since only numeric characters remain),
        # so that it sorts numerically instead of lexicographically.
        sortable_version = Cast(stripped_split_version, ArrayField(IntegerField()))
        return sortable_version

    def get_absolute_url(self):
        return reverse(
            "maven:mavenartifact_detail", kwargs={"group_id": self.group_id, "artifact_id": self.artifact_id}
        )

    def coordinates(self):
        return GACoordinates(self.group_id, self.artifact_id)

    def __str__(self):
        return str(self.coordinates())

    def __repr__(self):
        return f"{self.__class__.__name__}({str(self.coordinates())})"


class HasGAVCoordinates(ToolchainModel):
    """Base class for models that are identified uniquely by GAV coordinates."""

    class Meta:
        abstract = True
        unique_together = ("artifact", "version")

    artifact = ForeignKey(MavenArtifact, related_name="%(class)ss", on_delete=CASCADE)

    version = CharField(max_length=150)

    def coordinates(self):
        return GAVCoordinates(self.artifact.group_id, self.artifact.artifact_id, self.version)

    def __str__(self):
        return str(self.coordinates())

    def __repr__(self):
        return f"{self.__class__}({str(self.coordinates())})"


class MavenMetadata(ToolchainModel):
    """Represents a maven-metadata.xml file."""

    web_resource = OneToOneField(WebResource, related_name="maven_metadata", on_delete=CASCADE)


class POM(HasGAVCoordinates):
    """Represents a POM file."""

    web_resource = OneToOneField(WebResource, related_name="pom", on_delete=CASCADE)

    parent = ForeignKey("self", related_name="children", on_delete=CASCADE, null=True)

    @classmethod
    def for_gav_coordinates(cls, coordinates):
        try:
            return cls.objects.filter(
                artifact__group_id=coordinates.group_id,
                artifact__artifact_id=coordinates.artifact_id,
                version=coordinates.version,
            ).get()
        except POM.DoesNotExist:
            return None

    @classmethod
    def update_or_create(cls, coordinates, web_resource, parent=None):
        # Maven contains various irregular/non-canonical POM files that we want to ignore here.
        if web_resource.url != ArtifactLocator.pom_url(coordinates):
            raise PermanentWorkException(
                f"Non-canonical POM file path {web_resource.url} for coordinates {coordinates}."
            )
        artifact = MavenArtifact.objects.get_or_create(
            group_id=coordinates.group_id, artifact_id=coordinates.artifact_id
        )[0]
        cls.objects.update_or_create(
            artifact=artifact, version=coordinates.version, defaults={"web_resource": web_resource, "parent": parent}
        )

    def get_absolute_url(self):
        return reverse("maven:pom_detail", kwargs={"pk": self.pk})


class MavenArtifactVersion(HasGAVCoordinates):
    """A single version of a Maven artifact.

    May be populated in two steps:

      1. An instance with no metadata, just the GAV coordinates, is created
         when we first encounter a reference to an artifact version.
      2. Some time later the instance's metadata is fetched and updated.

    We update completed_at to the current timestamp after that second step has completed.
    """

    url = URLField(max_length=1024, blank=True)

    scm_url = URLField(max_length=1024, blank=True)

    packaging = CharField(max_length=30, blank=True)

    organization = ForeignKey(Organization, null=True, on_delete=CASCADE)

    licenses = ManyToManyField(License)

    direct_declared_dependencies = ManyToManyField(MavenArtifact, through="MavenDependency", blank=True)

    completed_at = DateTimeField(default=UNIX_EPOCH)

    @classmethod
    def for_coordinates(cls, coordinates):
        artifact = MavenArtifact.for_coordinates(coordinates)
        return cls.objects.get_or_create(artifact=artifact, version=coordinates.version)[0]

    @classmethod
    def get_available_versions(cls, artifact: MavenArtifact) -> list[str]:
        qs = cls.objects.get_or_create(artifact=artifact).values_list("version", flat=True)
        # Limiting the number of results here so we don't return unbound datasets.
        # Might need to be tweaked when we actually support maven.
        qs = qs.order_by("-version")[:100]
        return list(qs)

    def dependency_data(self):
        return MavenDependency.objects.filter(dependent=self)

    def get_absolute_url(self):
        return reverse(
            "maven:mavenartifactversion_detail",
            kwargs={
                "group_id": self.artifact.group_id,
                "artifact_id": self.artifact.artifact_id,
                "version": self.version,
            },
        )


class MavenDependency(ToolchainModel):
    """The through table for a MavenArtifactVersion's direct_declared_dependencies field.

    We use this instead of Django's implicit through table, so we can attach extra data.
    """

    class Meta:
        unique_together = ("dependent", "depends_on_artifact", "classifier")

    dependent = ForeignKey(MavenArtifactVersion, on_delete=CASCADE)

    # The version(s) are specified in the depends_on_version_spec field below.
    depends_on_artifact = ForeignKey(MavenArtifact, on_delete=CASCADE)

    # Specifies the version(s) of the depended-on artifact.
    # See https://maven.apache.org/pom.html#Dependency_Version_Requirement_Specification
    # for details on these specs.
    depends_on_version_spec = CharField(max_length=200)

    # See https://maven.apache.org/pom.html#Dependencies for details on the following fields.

    classifier = CharField(max_length=50, blank=True)

    type = CharField(max_length=50, blank=True)

    COMPILE = "compile"
    PROVIDED = "provided"
    RUNTIME = "runtime"
    TEST = "test"
    SYSTEM = "system"
    SCOPE_CHOICES = (choice(COMPILE), choice(PROVIDED), choice(RUNTIME), choice(TEST), choice(SYSTEM))

    scope = CharField(max_length=8, choices=SCOPE_CHOICES, default=COMPILE)

    optional = BooleanField(default=False)

    def __str__(self):
        return f"{self.dependent} -> {self.depends_on_artifact} (version_spec={self.depends_on_version_spec,}, classifier={self.classifier}, type={self.type}, scope={self.scope}, optional={self.optional})"


# Auxiliary tables to link resources with the data derived from processing them.
# May not be required for functionality, but useful for display and debugging.


class MavenMetadataVersion(ToolchainModel):
    """A one-to-many from MavenMetadata to MavenArtifactVersions found in that metadata.

    We don't make this a FK in MavenArtifactVersion, to keep the latter simple and independent, and because not every
    MavenArtifactVersion need come from a maven-metadata.xml files.
    """

    maven_metadata = ForeignKey(MavenMetadata, related_name="versions", on_delete=CASCADE)
    artifact_version = OneToOneField(MavenArtifactVersion, on_delete=CASCADE)


class POMArtifactVersion(ToolchainModel):
    """Links a POM with the artifact it describes."""

    pom = OneToOneField(POM, related_name="artifact_version_ref", on_delete=CASCADE)
    artifact_version = ForeignKey(MavenArtifactVersion, related_name="pom_refs", on_delete=CASCADE)


class MavenStats(ToolchainModel):
    """Stats about Maven artifacts."""

    # We shard rows to avoid lock contention.
    # Note that it's fine to change NUM_SHARDS at any time (even to reduce it).
    # No special migration is required.  It merely bounds the range in which
    # an update can randomly pick a shard.
    NUM_SHARDS = 64

    class Meta:
        unique_together = ("scope", "shard")

    # The scope these stats refer to. A blank value indicates global stats, a group_id (prefix) indicates
    # stats for that group (or all groups with that prefix), group_id:artifact_id indicates stats
    # for that artifact.  E.g., we store stats for '', 'com', 'com.twitter', 'com.twitter:ostrich'.
    scope = CharField(max_length=200, db_index=True, blank=True)
    shard = IntegerField()
    num_artifacts = IntegerField(default=0)  # Number of artifacts that have a metadata.xml with <versions>.
    num_versions = IntegerField(default=0)  # Number of versions in the <versions> of an artifact's metadata.xml.
    num_poms = IntegerField(default=0)  # Number of POM files (including those in versions not in <versions>).
    num_binary_jars = IntegerField(default=0)
    num_source_jars = IntegerField(default=0)
    num_javadoc_jars = IntegerField(default=0)

    @classmethod
    def for_scope(cls, scope):
        """Retrieve the stats for the given scope."""
        kwargs = {
            k: Sum(k)
            for k in [
                "num_artifacts",
                "num_versions",
                "num_poms",
                "num_binary_jars",
                "num_source_jars",
                "num_javadoc_jars",
            ]
        }
        return cls.objects.filter(scope=scope).aggregate(**kwargs)

    @classmethod
    def increment(cls, scope, **kwargs):
        """Add to the stats for the given scope (and all enclosing scopes).

        For each kwarg, the stat with that name is incremented by the value of the kwarg. E.g.,
        `MavenStats.increment_for_scope('foo.bar:baz', num_artifacts=1, num_versions=5)`.
        """
        group_id, _, artifact_id = scope.partition(":")
        if artifact_id:
            cls._increment_for_scope(scope, **kwargs)
            scope = group_id

        while scope:
            cls._increment_for_scope(scope, **kwargs)
            scope = scope.rpartition(".")[0]
        cls._increment_for_scope("", **kwargs)

    @classmethod
    def _increment_for_scope(cls, scope, **kwargs):
        # Pick a shard at random.
        shard = random.randint(0, cls.NUM_SHARDS - 1)  # nosec: B311
        update_kwargs = {k: F(k) + v for (k, v) in kwargs.items()}

        def update():
            return cls.objects.filter(scope=scope, shard=shard).update(**update_kwargs)

        n = update()
        if n == 0:
            # Note that we get_or_create, to avoid race conditions.
            cls.objects.get_or_create(scope=scope, shard=shard)
            update()

    def __str__(self):
        stats = ",".join(
            [
                f"{k}={self.__dict__[k]}"
                for k in [
                    "num_artifacts",
                    "num_versions",
                    "num_poms",
                    "num_binary_jars",
                    "num_source_jars",
                    "num_javadoc_jars",
                ]
            ]
        )
        return f"{self.scope}({stats})"
