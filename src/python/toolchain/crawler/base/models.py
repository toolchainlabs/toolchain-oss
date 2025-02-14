# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from django.db.models import (
    CASCADE,
    SET_NULL,
    CharField,
    ForeignKey,
    IntegerField,
    OneToOneField,
    Q,
    UniqueConstraint,
    URLField,
)
from django.urls import reverse
from django.utils.functional import cached_property

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.db.base_models import ToolchainModel
from toolchain.django.webresource.models import WebResource
from toolchain.workflow.models import WorkUnitPayload


class KytheEntriesBase(ToolchainModel):
    """A set of Kythe entries indexed from some set of source files."""

    class Meta:
        abstract = True

    # The location of the entries file (may be an http:// or s3:// url, for example).
    location = URLField(max_length=500, db_index=True, unique=True)

    UNCOMPRESSED = "UNCOMPRESSED"
    TAR = "TAR"
    ZIP = "ZIP"
    GZTAR = "GZTAR"
    BZTAR = "BZTAR"

    COMPRESSION_CHOICES = (
        (UNCOMPRESSED, "uncompressed"),
        (TAR, ".tar"),
        (ZIP, ".zip"),
        (GZTAR, ".tar.gz"),
        (BZTAR, ".tar.bz"),
    )

    @classmethod
    def get_compression_suffix(cls, compression):
        if compression == cls.UNCOMPRESSED:
            return ""
        else:
            for x in cls.COMPRESSION_CHOICES:
                if x[0] == compression:
                    return x[1]
        raise ToolchainAssertion(f"Unknown compression type {compression}")

    # How the file content is archived and/or compressed.
    compression = CharField(max_length=12, choices=COMPRESSION_CHOICES)


class URLWork(WorkUnitPayload):
    """A base class for work units that operate on a URL.

    Subclasses must provide a `url` property.
    """

    class Meta:
        abstract = True

    # Subclasses must provide an instance property of this name, e.g., a database field.
    url = None

    @property
    def description(self):
        return self.url

    @property
    def search_vector(self):
        return super().search_vector + [self.url.replace("/", " ")]


class FetchURL(URLWork):
    """Work unit to fetch the contents of a URL and create a WebResource to represent it."""

    class Meta:
        # We allow only one pending fetch (i.e., one with a NULL web_resource) per url. However many fetches of the
        # same url may result in the same web_resource, so the (url, web_resource) pair need not be unique when
        # web_resource is not NULL.
        constraints = [
            UniqueConstraint(fields=["url"], name="single_pending_fetch", condition=Q(web_resource__isnull=True))
        ]

    url = URLField(max_length=500, db_index=True)

    last_http_status = IntegerField(db_index=True, null=True)

    # The web resource representing the content of the URL at the time it was fetched.
    web_resource = ForeignKey(WebResource, db_index=True, null=True, on_delete=SET_NULL)

    @classmethod
    def get_or_create(cls, url: str) -> FetchURL:
        return cls.objects.get_or_create(url=url)[0]

    def get_absolute_url(self):
        return reverse("crawler:crawler_base:fetchurl_detail", args=[self.pk])


class WebResourceWork(URLWork):
    """A base class for work units that operate on a WebResource."""

    class Meta:
        abstract = True

    web_resource = OneToOneField(WebResource, db_index=True, on_delete=CASCADE)

    @cached_property
    def url(self):
        return self.web_resource.url
