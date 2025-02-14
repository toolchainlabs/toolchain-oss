# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import re

from toolchain.packagerepo.maven.xml_namespace_util import pom_ns_map


class POMPropertySubstitutor:
    """Class to perform property placeholder substitutions in POM files.

    See https://maven.apache.org/pom.html#Properties.
    """

    class Error(Exception):
        pass

    # A regex matching placeholders of the form ${name}.
    _placeholder_re = re.compile(r"\$\{[^}]+\}")

    def __init__(self, project):
        """:param project: the root XML element of a POM file."""
        self._project = project

    def substitute(self, text):
        """Replace all property placeholders with their values."""
        # Iterate until stable value achieved.
        i = 0
        prev = None
        ret = text
        while ret != prev:
            prev = ret
            ret = self._placeholder_re.sub(self._substitute_match, ret)
            i += 1
            if i == 50:
                raise self.Error(f"Too many iterations while interpolating {text}")
        return ret

    def _substitute_match(self, matchobj):
        key = matchobj.group(0)[2:-1]  # Strip off the ${ prefix and the } suffix.
        return self.get(key, key)

    def get(self, name, default):
        """Return the substition for the property with the given name.

        If unknown, return the default.
        """
        # There are 5 styles of property, as described in https://maven.apache.org/pom.html#Properties.

        # Styles 4 and 5.
        # We assume that any unprefixed property name is a reference into <properties> (style 5).
        # Hypothetically it could also be a JVM system property (style 4).  But it's highly unlikely
        # that POM files describing published artifacts would rely on JVM runtime state.
        #
        # NOTE: Properties in the <properties> element take precedence (e.g., if both
        # <properties><project.foo>...</project.foo></properties> and <project><foo>...</foo></project>
        # exist, then ${project.foo} references the former.  Such cases exist in practice
        # (e.g., https://repo1.maven.org/maven2/org/kuali/kpme/kpme/2.1.0/kpme-2.1.0.pom).
        ret = self._project.find(f"./pom:properties/pom:{name}", pom_ns_map)
        if ret is not None:
            return ret.text

        # Style 2.
        if name.startswith("project."):
            name_part = name[7:].replace(".", "/pom:")
            ret = self._project.find(f".{name_part}", pom_ns_map)
            if ret is not None:
                return ret.text

        # Style 1.
        if name.startswith("env."):
            # It's highly unlikely that POM files describing published artifacts would rely
            # on the environment, but let's detect it just in case.
            raise NotImplementedError("${env.*} properties are not supported.")

        # Style 3.
        if name.startswith("settings."):
            # It's unclear if POM files describing published artifacts would rely
            # on a settings.xml file.  We catch this for now until we're sure one way or the other.
            raise NotImplementedError("${settings.*} properties are not supported.")

        return default
