# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from xml.etree import ElementTree

from toolchain.packagerepo.maven.xml_chain import XMLChainLink
from toolchain.packagerepo.maven.xml_parsing_mixin import XMLParsingMixin


class TestXMLChain:
    ns_url = "http://toolchainlabs.com/test_namespace"
    ns_map = {"sc": ns_url}

    superdoc = ElementTree.fromstring(
        f"""
        <root xmlns="{ns_url}">
          <name>SUPER</name>
          <foo>FOO</foo>
          <bar>
            <baz>SUPERBAZ</baz>
            <qux>QUX1</qux>
            <qux>QUX2</qux>
          </bar>
        </root>
        """
    )

    subdoc = ElementTree.fromstring(
        f"""
        <root xmlns="{ns_url}">
          <name>SUB</name>
          <bar>
            <baz>SUBBAZ</baz>
            <quux>QUUX</quux>
          </bar>
          <corge>CORGE</corge>
        </root>
        """
    )

    # Test directly against the find() method.
    def test_find(self):
        chain = XMLChainLink(self.subdoc, XMLChainLink(self.superdoc, None))

        def find_text(path):
            return chain.find(path, self.ns_map).text

        assert find_text("./sc:foo") == "FOO"  # Only in the superdoc.
        assert find_text("./sc:corge") == "CORGE"  # Only in the subdoc.
        assert find_text("./sc:name") == "SUB"  # Subdoc takes precedence over superdoc.

        assert find_text("./sc:bar/sc:qux") == "QUX1"  # Only (the first appearance) in the superdoc.
        assert find_text("./sc:bar/sc:quux") == "QUUX"  # Only in the subdoc.
        assert find_text("./sc:bar/sc:baz") == "SUBBAZ"  # Subdoc takes precedence over superdoc.

    # Test directly against the findall() method.
    def test_findall(self):
        chain = XMLChainLink(self.subdoc, XMLChainLink(self.superdoc, None))

        def findall_text(path):
            return [x.text for x in chain.findall(path, self.ns_map)]

        assert findall_text("./sc:foo") == ["FOO"]  # Only in the superdoc.
        assert findall_text("./sc:name") == ["SUB", "SUPER"]  # Aggregates subdoc and superdoc values.
        assert findall_text("./sc:bar/sc:qux") == ["QUX1", "QUX2"]  # All appearances in the superdoc.

    def test_xml_parsing_mixin(self):
        class P(XMLParsingMixin):
            document_element = XMLChainLink(self.subdoc, XMLChainLink(self.superdoc, None))
            ns_map = self.ns_map
            ns = "sc"

        p = P()

        # Note that the semantics of child_text_map are "find the first match for parent, then find its direct children".
        # Therefore our value for qux is empty - our first match for ./bar is in the subdoc.
        assert p.child_text_map("./bar", ["qux", "quux"]) == {"qux": "", "quux": "QUUX"}

        # Note that the semantics of child_text_maps are "find all matches for parent, and then find the direct children of
        # each", so in this case we do have entries for both the subdoc and the superdoc.
        assert p.child_text_maps("./bar", ["qux", "baz"]) == [
            {"qux": "", "baz": "SUBBAZ"},
            {"qux": "QUX1", "baz": "SUPERBAZ"},
        ]
