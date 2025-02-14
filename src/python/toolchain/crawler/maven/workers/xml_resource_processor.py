# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.crawler.base.web_resource_processor import WebResourceProcessor
from toolchain.crawler.maven.maven_schedule_util import MavenScheduleUtil
from toolchain.packagerepo.maven.coordinates import GACoordinates, GAVCoordinates
from toolchain.packagerepo.maven.xml_parsing_mixin import XMLParsingError, XMLParsingMixin
from toolchain.workflow.error import PermanentWorkException


class XMLResourceProcessor(XMLParsingMixin, WebResourceProcessor):
    """Base class for classes that handle Maven XML web resources."""

    schedule_util_cls = MavenScheduleUtil

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._document_element = None

    @classmethod
    def parse_web_resource(cls, web_resource):
        """Parse a web resource as XML and return the root element."""
        try:
            with web_resource.content_reader() as fp:
                return cls.parse(fp.read())
        except XMLParsingError as e:
            raise PermanentWorkException(f"XML parsing error for {web_resource.url}: {e!r}")

    @property
    def document_element(self):
        return self._document_element

    def process(self):
        self._document_element = self.create_document_element()
        if self._document_element is None:
            return False  # So that work necessary to generate a document element can be scheduled.
        return self.process_xml()

    def create_document_element(self):
        """Subclasses can override to provide a document element some other way."""
        return self.parse_web_resource(self.web_resource)

    def process_xml(self):
        """Subclasses implement this to handle the xml document.

        Exceptions and return values are as documented for `toolchain.workflow.worker.Worker#do_work`.
        """
        raise NotImplementedError()

    def ga_coordinates_from_xml(self, path):
        """Helper method for subclasses to use to extract GA coordinates from an xml element."""
        args_map = self.child_text_map(path, ["groupId", "artifactId"])
        if args_map is None:
            return None
        return GACoordinates(args_map["groupId"], args_map["artifactId"])

    def gav_coordinates_from_xml(self, path):
        """Helper method for subclasses to use to extract GAV coordinates from an xml element."""
        args_map = self.child_text_map(path, ["groupId", "artifactId", "version"])
        if args_map is None:
            return None
        return GAVCoordinates(args_map["groupId"], args_map["artifactId"], args_map["version"])
