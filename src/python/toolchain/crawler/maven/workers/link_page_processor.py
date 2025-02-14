# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from html.parser import HTMLParser
from urllib.parse import urljoin

from toolchain.crawler.base.web_resource_processor import WebResourceProcessor
from toolchain.crawler.maven.maven_schedule_util import MavenScheduleUtil
from toolchain.crawler.maven.models import ProcessLinkPage
from toolchain.django.webresource.models import WebResourceLink
from toolchain.packagerepo.maven.artifact_locator import ArtifactLocator
from toolchain.packagerepo.maven.models import MavenStats


class LinkFinderParser(HTMLParser):
    """An HTML parser that collects all the links from <a> elements in a document."""

    def __init__(self):
        HTMLParser.__init__(self)  # HTMLParser is an old-style class, so we can't use super().
        self._links = []

    @property
    def links(self):
        return self._links

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            try:
                href = [attr for attr in attrs if attr[0] == "href"][0][1]
                if not href.startswith(".."):
                    # Ignore links up the hierarchy, so we don't crawl the entire tree while testing on a subtree.
                    self._links.append(href)
            except IndexError:
                pass


class LinkPageProcessor(WebResourceProcessor):
    """Handler for HTML pages of links to Maven resources."""

    schedule_util_cls = MavenScheduleUtil

    DEFAULT_LEASE_SECS = 900  # Some link pages (e.g., https://repo1.maven.org/maven2/com/) can be very large.

    work_unit_payload_cls = ProcessLinkPage

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._links = []  # List of url strings.

    def process(self):
        parser = LinkFinderParser()
        parser.feed(self.web_resource.get_content_as_text())
        for link in parser.links:
            link_url = urljoin(self.web_resource.url, link)
            self._links.append(link_url)
        return True

    def on_success(self, work_unit_payload):
        wr_links = [WebResourceLink(source=self.web_resource, target=link) for link in self._links]
        WebResourceLink.objects.filter(source=self.web_resource).delete()
        WebResourceLink.objects.bulk_create(wr_links, batch_size=1000)
        self.schedule_util.schedule_fetches(self._links)
        self.update_stats()

    def update_stats(self):
        num_binary_jars = 0
        num_source_jars = 0
        num_javadoc_jars = 0
        num_poms = 0
        for link in self._links:
            if link.endswith(".pom"):
                num_poms += 1
            if link.endswith(".jar"):
                if link.endswith("-sources.jar"):
                    num_source_jars += 1
                elif link.endswith("-javadoc.jar"):
                    num_javadoc_jars += 1
                else:
                    num_binary_jars += 1
        if num_binary_jars or num_source_jars or num_javadoc_jars:
            gav_coords = ArtifactLocator.parse_artifact_version_url(self.web_resource.url)
            MavenStats.increment(
                f"{gav_coords.group_id}:{gav_coords.artifact_id}",
                num_poms=num_poms,
                num_binary_jars=num_binary_jars,
                num_source_jars=num_source_jars,
                num_javadoc_jars=num_javadoc_jars,
            )
