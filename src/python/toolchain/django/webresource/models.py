# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import gzip
import logging
import os
import shutil
from contextlib import contextmanager
from io import BytesIO

import requests
from django.db.models import (
    CASCADE,
    AutoField,
    BinaryField,
    CharField,
    DateTimeField,
    F,
    ForeignKey,
    Func,
    Index,
    URLField,
)
from django.db.models.functions import Substr
from django.urls import reverse

from toolchain.aws.s3 import S3
from toolchain.base.fileutil import safe_file_create
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.db.base_models import ToolchainModel
from toolchain.django.db.transaction_broker import TransactionBroker

transaction = TransactionBroker("webresource")


logger = logging.getLogger(__name__)


class WebResource(ToolchainModel):
    """A version of a web resource."""

    DEFAULT_ETAG = "Not Set"

    class Meta:
        unique_together = ("url", "sha256_hexdigest")

        indexes = [Index(fields=["url", "freshness"])]

        get_latest_by = "freshness"

    class UnknownEncoding(ToolchainAssertion):
        def __init__(self, url):
            super().__init__(f"Unknown encoding for {url}")

    id = AutoField(primary_key=True)
    url = URLField(max_length=500, db_index=True)

    sha256_hexdigest = CharField(max_length=64, db_index=True)

    # A timestamp at which this web resource was known to contain the content referenced in this object.
    freshness = DateTimeField(null=True)

    encoding = CharField(max_length=20, blank=True)  # Blank if content is not text, or if encoding unknown.

    etag = CharField(max_length=100, default=DEFAULT_ETAG)

    # If provided, the url of a resource containing the same content as this web resource
    # This will typically be a file on a shared, remote filesystem such as S3.
    # Obviously the content can be read directly from this web resource's url field, but it is
    # often more practical to copy the content to a local or remote file, and process it
    # from there later.
    #
    # You won't usually access this directly. Use content_reader() instead.
    content_url = CharField(max_length=1024, blank=True)

    # If provided, the content of this web resource.
    # Typically only populated for small text fields.
    # You won't usually access this directly. Use content_reader() instead.
    content = BinaryField(null=True)

    # The compression applied to content (or the data at content_url), if any.
    # We may choose to compress content to save space.
    # Note that this is distinct from any compression the server may have applied (and reported
    # via the Content-Encoding header) when fetching the content.

    # Currently we only support gzip or no compression.
    GZIP = "gz"
    IDENTITY = "id"
    _compression_choices = ((GZIP, "gzip"), (IDENTITY, "identity"))
    compression = CharField(max_length=2, choices=_compression_choices)

    def get_status(self):
        crawled = self.has_content()
        exists = crawled or self.resource_exists(self.url)
        return exists, crawled

    @classmethod
    def latest_by_url(cls, url: str) -> WebResource | None:
        try:
            return cls.objects.filter(url=url).latest()
        except cls.DoesNotExist:
            return None

    @classmethod
    def resource_exists(cls, url):
        # TODO: This doesn't mean that the resource exists at this object's version.
        # Clarify via a name change.
        return requests.head(url).status_code == 200

    @classmethod
    def act_on_shard(cls, shard, action_func):
        """Apply an action function to a shard's worth of URLs.

        :param int shard: The shard to act on (mod 4096).
        :param callable action_func: The function to call on each web resource.
        """
        logger.info(f"Acting on shard {shard}")
        # Force Django to open a new connection and not try to use one that may
        # have been closed on the server side.
        transaction.connection.close()
        shard = shard % 4096
        shard_str = f"{shard:03x}"
        i = 0
        for wr in cls.objects.annotate(shard=Substr(Func(F("url"), function="md5"), 1, 3)).filter(shard=shard_str):
            action_func(wr)
            i += 1
        logger.info(f"Acted on {i} web resources for shard {shard}")

    def has_content(self):
        return self.content_url or self.content is not None

    @property
    def is_text(self) -> bool:
        return bool(self.encoding)

    def get_content_as_text(self):
        """Return this resource's content, as decoded text.

        Content is assumed to be short enough to be returned in a single string.

        Raises UnknownEncoding if the content isn't text, or its encoding isn't known.
        """
        if not self.is_text:
            raise self.UnknownEncoding(self.url)
        with self.content_reader() as fp:
            return fp.read().decode(self.encoding)

    def get_absolute_url(self):
        # TODO: Get rid of this reference to `maven`.
        return reverse("maven:webresource_detail", kwargs={"pk": self.pk})

    @contextmanager
    def content_reader(self):
        """Yields a file-like object that will read over the content of this resource.

        The content will be decompressed if necessary.
        """
        with self._raw_content_reader() as fp:
            if self.compression == self.GZIP:
                yield gzip.GzipFile(mode="rb", fileobj=fp)
            else:
                yield fp

    @contextmanager
    def _raw_content_reader(self):
        """Yields a file-like object that will read over the raw content of this resource.

        The raw content may be compressed.
        """
        if self.content is not None:
            yield BytesIO(self.content)
            return

        if not self.content_url:
            raise ToolchainAssertion(f"WebResource {self} has neither content nor content_url!")

        bucket, key = S3.parse_s3_url(self.content_url)
        with S3().body_reader(bucket, key) as streaming_body:
            yield streaming_body

    def dump_content(self, filepath: str) -> None:
        if self.content is not None:
            with safe_file_create(filepath) as tmpfile:
                with open(tmpfile, "wb") as fp:
                    fp.write(self.content)
                return
        self._download_content(filepath)

    def _download_content(self, filepath: str) -> None:
        if not self.content_url:
            raise ToolchainAssertion(f"WebResource {self!r} has neither content nor content_url!")
        bucket, key = S3.parse_s3_url(self.content_url)
        with safe_file_create(filepath) as tmpfile:
            tmpfile_raw = f"{tmpfile}.raw"
            try:
                logger.info(f"download content from {self.content_url} into {filepath}")
                S3().download_file(bucket, key, tmpfile_raw)
                if self.compression == self.GZIP:
                    with gzip.open(tmpfile_raw, "rb") as infile, open(tmpfile, "wb") as outfile:
                        shutil.copyfileobj(infile, outfile)
                else:
                    os.rename(tmpfile_raw, tmpfile)
            finally:
                if os.path.exists(tmpfile_raw):
                    os.unlink(tmpfile_raw)

    def __str__(self):
        return self.url

    def __repr__(self):
        return f"WebResource {self.id}"


class WebResourceLink(ToolchainModel):
    """A link from a web resource to some URL."""

    class Meta:
        unique_together = ("source", "target")

    id = AutoField(primary_key=True)
    source = ForeignKey(WebResource, related_name="links_from", on_delete=CASCADE)
    # target is just a URL and not a FK to WebResource, because we may or may not want to follow the link.
    target = URLField(max_length=500, db_index=True)
