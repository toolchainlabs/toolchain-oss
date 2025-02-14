# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import re
from urllib.parse import urlparse, urlunparse

from toolchain.packagerepo.maven.coordinates import GACoordinates, GAVCoordinates


class ArtifactLocator:
    """Utility class for computing URLs for Maven artifacts."""

    _URL_ROOT_PREFIX = "https://repo1.maven.org/maven2"

    _artifact_re = re.compile(rf"^{_URL_ROOT_PREFIX}/(?P<group_id>.+)/(?P<artifact_id>[^/]+)/.*$")

    _artifact_version_re = re.compile(
        rf"^{_URL_ROOT_PREFIX}/(?P<group_id>.+)/(?P<artifact_id>[^/]+)/(?P<version>[^/]+)/.*$"
    )

    @classmethod
    def parse_artifact_url(cls, url):
        """Return the GA coordinates for a URL relating to some artifact."""
        mo = cls._artifact_re.match(url)
        if mo:
            return GACoordinates(mo.group("group_id").replace("/", "."), mo.group("artifact_id"))
        return None

    @classmethod
    def parse_artifact_version_url(cls, url):
        """Return the GAV coordinates for a URL relating to some artifact version."""
        mo = cls._artifact_version_re.match(url)
        if mo:
            return GAVCoordinates(mo.group("group_id").replace("/", "."), mo.group("artifact_id"), mo.group("version"))
        return None

    @classmethod
    def parent_link_page_url(cls, url):
        parts = urlparse(url)
        parent_parts = parts[0:2] + (parts[2][0 : parts[2].rfind("/", 0, -1) + 1],) + parts[3:]
        return urlunparse(parent_parts)

    @classmethod
    def maven_metadata_url(cls, ga):
        """Compute the URL at which we can find the maven-metadata.xml file for the given GA coordinates.

        :param ga: Any object with 'group_id' and 'artifact_id' properties.
        """
        return f"{cls._url_prefix_for_artifact(ga)}/maven-metadata.xml"

    @classmethod
    def pom_url(cls, ga, version=None):
        """Compute the URL at which we can find the pom file for the given GA coordinates and version.

        :param ga: Any object with 'group_id' and 'artifact_id' properties.
        :param version: A maven version string.
                        If unspecified, `ga` is assumed to also have a 'version' property.
        """
        return "{prefix}/{version}/{artifact_id}-{version}.pom".format(
            prefix=cls._url_prefix_for_artifact(ga),
            artifact_id=ga.artifact_id,
            version=ga.version if version is None else version,
        )

    @classmethod
    def binary_jar_url(cls, gav):
        """Compute the URL at which we can find the binary jar for the given GAVCoordinates."""
        # We currently assume that all artifacts are jar files.  The packaging type is mentioned in the
        # MavenArtifactVersion, but we've seen cases where it's mis-specified (e.g., in https://repo1.maven.org/maven2/
        # com/fasterxml/jackson/dataformat/jackson-dataformat-xml/2.8.8/jackson-dataformat-xml-2.8.8.pom,
        # the packaging elements says "bundle", but the artifact is a jar).
        return "{prefix}/{version}/{artifact_id}-{version}.jar".format(
            prefix=cls._url_prefix_for_artifact(gav), artifact_id=gav.artifact_id, version=gav.version
        )

    @classmethod
    def source_jar_url(cls, gav):
        """Compute the URL at which we can find the source jar for the given GAVCoordinates."""
        return "{prefix}/{version}/{artifact_id}-{version}-sources.jar".format(
            prefix=cls._url_prefix_for_artifact(gav), artifact_id=gav.artifact_id, version=gav.version
        )

    @classmethod
    def _url_prefix_for_artifact(cls, ga):
        """Returns the URL of the directory containing all metadata for the given artifact.

        :param ga: Any object with 'group_id' and 'artifact_id' properties.
        """
        group_path = "/".join(ga.group_id.split("."))
        return f"{cls._URL_ROOT_PREFIX}/{group_path}/{ga.artifact_id}"
