# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import functools
from collections.abc import Iterable
from typing import Any

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.db.models import (
    CASCADE,
    AutoField,
    CharField,
    ForeignKey,
    IntegerField,
    JSONField,
    OneToOneField,
    Q,
    URLField,
)
from django.urls import reverse

from toolchain.base.toolchain_error import ToolchainAssertion, ToolchainError
from toolchain.django.db.base_models import ToolchainModel
from toolchain.django.webresource.models import WebResource
from toolchain.lang.python.distributions.distribution_key import canonical_project_name
from toolchain.lang.python.distributions.distribution_type import DistributionType
from toolchain.packagerepo.pypi.util import url_for_project

# See https://packaging.python.org/glossary/ for terminology.

# A project is occasionally referred to as a "package" in PyPI API documentation, but since the term "package"
# has another meaning in Python (a directory containing modules), we standardize on "project" here.


class InvalidDistError(ToolchainError):
    pass


class Project(ToolchainModel):
    MAX_PROJECT_NAME = 256
    id = AutoField(primary_key=True)
    name = CharField(max_length=MAX_PROJECT_NAME, unique=True, db_index=True)

    @property
    def pypi_url(self):
        return url_for_project(self.name)

    @classmethod
    def get_or_create(cls, name: str) -> Project:
        canonical_name = canonical_project_name(name)
        if len(name) > cls.MAX_PROJECT_NAME:
            raise InvalidDistError(f"Project name to long: {name=}")
        return cls.objects.get_or_create(name=canonical_name)[0]

    def get_absolute_url(self) -> str:
        return reverse("pypi:project_detail", args=[self.pk])

    def __repr__(self) -> str:
        return f"Project({self.name})"

    def __str__(self) -> str:
        return self.name


class Release(ToolchainModel):
    class Meta:
        unique_together = [("project", "version")]

    id = AutoField(primary_key=True)
    project = ForeignKey(Project, related_name="releases", on_delete=CASCADE)
    version = CharField(max_length=100)

    @classmethod
    def get_or_create(cls, project: Project, version: str) -> Release:
        return cls.objects.get_or_create(project=project, version=version)[0]

    @classmethod
    def for_module(cls, module: str) -> Iterable[Release]:
        return cls.objects.filter(distributions__modules__contains=[module])

    def get_absolute_url(self) -> str:
        return reverse("pypi:release_detail", args=[self.pk])

    def __repr__(self) -> str:
        return f"Release({self.project_id}, {self.version})"

    def __str__(self) -> str:
        # Check if the project has already been fetched, use its name if so, or its id if not.
        # This avoids triggering a db roundtrip just to generate a __str__.
        # Note that we don't do the same trick for __repr__, since that is expected to be consistent.
        package = self.project.name if "project" in self._state.fields_cache else f"project #{self.project_id}"
        return f"{package} {self.version}"


class Distribution(ToolchainModel):
    id = AutoField(primary_key=True)
    release = ForeignKey(Release, on_delete=CASCADE, related_name="distributions")
    filename = CharField(max_length=300, unique=True, db_index=True)
    url = URLField(max_length=500, unique=True)
    dist_type = CharField(max_length=20, choices=DistributionType.django_model_field_choices())
    # The distribution is known to exist in the serial range [serial_from, serial_to).
    # serial_to will typically be None, unless the distribution was deleted.
    serial_from = IntegerField(db_index=True)
    serial_to = IntegerField(db_index=True, null=True)

    @classmethod
    def get_or_create(cls, release: Release, filename: str, url: str, dist_type: str, serial_from: int) -> Distribution:
        return cls.objects.get_or_create(
            defaults={"serial_from": serial_from}, release=release, filename=filename, url=url, dist_type=dist_type
        )[0]

    @classmethod
    def get_or_create_from_dict(cls, dist_dict: dict[str, Any], release: Release, serial_from: int) -> Distribution:
        """Get or create using data from a dict.

        The keys in the dict should be those found in the PyPI JSON API dict describing a distribution, except that it
        should also contain a dist_type key, whose value is converted from the original packagetype field.
        """
        dist_url = f'{dist_dict["url"]}#sha256={dist_dict["digests"]["sha256"]}'
        return cls.get_or_create(
            release=release,
            filename=dist_dict["filename"],
            url=dist_url,
            dist_type=dist_dict["dist_type"],
            serial_from=serial_from,
        )

    @classmethod
    def get_urls(cls, dist_specs: list[dict]) -> None:
        """Get the URLs for the specified distributions.

        Each spec is expected to be a dict containing the keys 'project_name', 'version', 'sha256'. This method updates
        each dict, adding a key 'url'.

        Useful for turning resolver results into URLs.
        """
        clauses = []
        for dist_spec in dist_specs:
            clauses.append(
                Q(release__project__name=canonical_project_name(dist_spec["project_name"]))
                & Q(release__version=dist_spec["version"])
                & Q(url__endswith=dist_spec["sha256"])
            )
        disjunction = functools.reduce(lambda a, b: a | b, clauses)
        # NB: The last 64 bytes of the URL are the sha256.
        res = {url[-64:]: url for url in cls.objects.filter(disjunction).values_list("url", flat=True)}
        for dist_spec in dist_specs:
            url = res.get(dist_spec["sha256"])
            if not url:
                raise ToolchainError(
                    f"No distribution found for {dist_spec['project_name']} {dist_spec['version']} "
                    f"with sha256={dist_spec['sha256']}"
                )
            dist_spec["url"] = url

    @classmethod
    def get_url_for_locked_version(cls, project_name: str, version: str, sha256: str) -> str | None:
        """Get the URL for the distribution from the given release with the given sha256.

        Useful for turning lockfile entries into URLs.
        """
        dist_spec = {"project_name": project_name, "version": version, "sha256": sha256}
        cls.get_urls([dist_spec])
        return dist_spec["url"]

    def get_absolute_url(self) -> str:
        return reverse("pypi:distribution_detail", args=[self.pk])

    def __repr__(self) -> str:
        return f"Distribution({self.filename})"

    def __str__(self) -> str:
        return self.filename


class DistributionData(ToolchainModel):
    """Information about a Distribution, derived from actually fetching and analyzing it."""

    class Meta:
        indexes = [GinIndex(fields=["metadata"]), GinIndex(fields=["modules"])]

    id = AutoField(primary_key=True)
    distribution = OneToOneField(Distribution, on_delete=CASCADE, db_index=True, related_name="data")
    web_resource = OneToOneField(WebResource, on_delete=CASCADE, db_index=True)
    metadata = JSONField()
    modules = ArrayField(base_field=CharField(max_length=100))

    @classmethod
    def update_or_create(
        cls, distribution: Distribution, web_resource: WebResource, metadata: dict, modules: list
    ) -> DistributionData:
        return cls.objects.update_or_create(
            {"web_resource": web_resource, "metadata": metadata, "modules": modules}, distribution=distribution
        )[0]

    @classmethod
    def get_data_shard(cls, shard: int, num_shards: int, serial_from: int, serial_to: int) -> list[tuple]:
        """Return a useful subset of the data for a shard's worth of objects.

        Useful for further processing the data into efficient data structures for serving.
        """
        # We shard by either 1- or 2-hex digit prefix.
        if num_shards == 1:
            shard_hex = ""
        elif num_shards == 16:
            shard_hex = f"{shard:01x}"
        elif num_shards == 256:
            shard_hex = f"{shard:02x}"
        else:
            raise ToolchainAssertion("Number of shards must be either 1, 16 or 256")

        if not 0 <= shard < num_shards:
            raise ToolchainAssertion(f"Shard must be in the range [0, {num_shards})")

        # WebResource.sha256_hexdigest is indexed, so sharding by a prefix of it is an
        # efficient way to cut down the result size, if necessary.
        qs = cls.objects.filter(distribution__serial_from__gte=serial_from, distribution__serial_from__lt=serial_to)
        qs = qs.filter(Q(distribution__serial_to__isnull=True) | Q(distribution__serial_to__gte=serial_to))
        if shard_hex:
            qs = qs.filter(web_resource__sha256_hexdigest__startswith=shard_hex)
        qs = qs.values_list(
            "distribution__filename",
            "distribution__release__project__name",
            "distribution__release__version",
            "distribution__dist_type",
            "web_resource__sha256_hexdigest",
            "metadata__requires",
            "metadata__requires_dist",
            "metadata__requires_python",
            "modules",
        )
        return list(qs)

    @classmethod
    def for_module(cls, module):
        return cls.objects.filter(modules__contains=[module])

    def get_absolute_url(self) -> str:
        return reverse("pypi:distributiondata_detail", args=[self.pk])

    def __repr__(self) -> str:
        return f"DistributionData({self.id})"

    def __str__(self) -> str:
        # Check if the distribution has already been fetched, use its name if so, or its id if not.
        # This avoids triggering a db roundtrip just to generate a __str__.
        # Note that we don't do the same trick for __repr__, since that is expected to be consistent.
        return (
            f"{self.distribution} data"
            if "distribution" in self._state.fields_cache
            else f"distribution #{self.distribution_id} data"
        )
