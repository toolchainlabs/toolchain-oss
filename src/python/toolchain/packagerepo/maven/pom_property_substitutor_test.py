# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from xml.etree import ElementTree

import pytest

from toolchain.packagerepo.maven.pom_property_substitutor import POMPropertySubstitutor


class TestPOMPropertySubstitutor:
    xml = """
      <project xmlns="http://maven.apache.org/POM/4.0.0"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
               http://maven.apache.org/maven-v4_0_0.xsd">
        <properties>
          <prop1>hello</prop1>
          <prop2>world</prop2>
        </properties>
        <foo>
          <bar>baz</bar>
        </foo>
        <qux>quux</qux>
      </project>
  """

    @pytest.fixture()
    def subber(self):
        project = ElementTree.fromstring(self.xml)
        return POMPropertySubstitutor(project)

    def test_get(self, subber):
        def do_test(expected_value, name):
            assert expected_value == subber.get(name, "default")

        # Style #2 properties, as described in https://maven.apache.org/pom.html#Properties.
        do_test("baz", "project.foo.bar")
        do_test("quux", "project.qux")
        do_test("default", "project.foo.qux")

        # Style #5 properties, as described in https://maven.apache.org/pom.html#Properties.
        do_test("hello", "prop1")
        do_test("world", "prop2")

        # We don't support other properties styles.

    def test_substitute(self, subber):
        def do_test(expected_text, original_text):
            assert expected_text == subber.substitute(original_text)

        do_test("hello, world!", "${prop1}, ${prop2}!")
        do_test("What does baz mean?", "What does ${project.foo.bar} mean?")
