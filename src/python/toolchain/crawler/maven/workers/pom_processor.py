# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.utils.functional import cached_property

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.crawler.maven.workers.xml_resource_processor import XMLResourceProcessor
from toolchain.packagerepo.maven.coordinates import GAVCoordinates
from toolchain.packagerepo.maven.pom_property_substitutor import POMPropertySubstitutor
from toolchain.packagerepo.maven.xml_chain import XMLChainLink
from toolchain.packagerepo.maven.xml_namespace_util import pom_ns, pom_ns_map
from toolchain.workflow.error import PermanentWorkException


class POMProcessor(XMLResourceProcessor):
    """Base class for workers that process POM files."""

    ns_map = pom_ns_map

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._substitutor = None

    @property
    def substitutor(self):
        return self._substitutor.substitute

    def process_xml(self):
        self._substitutor = POMPropertySubstitutor(self.document_element)
        model_version = self.text("./modelVersion")
        if model_version != "4.0.0":
            raise PermanentWorkException(f"POM does not declare modelVersion 4.0.0: {self.web_resource.url}")
        return self.process_pom()

    def process_pom(self):
        """Subclasses implement this to handle the POM.

        Exceptions and return values are as documented for `toolchain.workflow.worker.Worker#do_work`.
        """
        raise NotImplementedError()

    def get_xml_chain(self, pom):
        if not pom:
            return None
        # TODO: Local cache of pom -> parent mappings, to save on database queries for shared grandparents?
        return XMLChainLink(self.parse_web_resource(pom.web_resource), self.get_xml_chain(pom.parent))

    @cached_property
    def ns(self):
        # We've seen some POM files (e.g., https://repo1.maven.org/maven2/junit/junit/4.1/junit-4.1.pom)
        # that omit the xmlns attribute, and effectively don't use POM's namespace.
        tag = self.document_element.find(".").tag
        # Note: The inner {} is replaced with the ns url, the outer double braces are replaced with
        # single braces, yielding the expected '{http://maven.apache.org/POM/4.0.0}'.
        if tag.startswith(f"{{{pom_ns_map.get(pom_ns)}}}"):
            return pom_ns
        return None

    def get_gav_coordinates(self):
        """Returns the GAV coordinates for the artifact version described by the POM file."""
        # We may inherit groupId and version (but not artifactId) from the parent POM.
        # We don't need to actually parse the parent POM to get those, because we know them from our own
        # parent specification.  If the content of a parent POM specified a different groupId or version
        # from the ones it was requested with, that would be chaos!  So we assume it never happens.
        own_gav_coordinates = self.gav_coordinates_from_xml(".")
        parent_gav_coordinates = self.gav_coordinates_from_xml("./parent")
        ret = GAVCoordinates(
            own_gav_coordinates.group_id or parent_gav_coordinates.group_id,
            own_gav_coordinates.artifact_id,
            own_gav_coordinates.version or parent_gav_coordinates.version,
        )
        if not (ret.group_id and ret.artifact_id and ret.version):
            raise ToolchainAssertion(f"Invalid GAV coordinates: {ret}")
        return ret
