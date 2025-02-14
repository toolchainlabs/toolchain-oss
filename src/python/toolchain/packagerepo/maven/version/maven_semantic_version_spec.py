# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import re

from toolchain.packagerepo.maven.version.maven_semantic_version import MavenSemver

# The SPEC_REGEX below matches any of the following:
# A Version Range - eg: '[1.0,4.2-beta)', '[,2-foo.0)', '[.9,]'
#   left_range: one of '(' or '['
#   lower_bound: 0 or more characters that are not ',', ']' or ')' eg: '1.0-alpha'
#   a literal ','
#   upper_bound: 0 or more characters that are not ]' or ')'
#   right_range: one of ')' or '['
# A Hard Requirement - eg: '[1.0]'
#   '['
#   hard_requirement: 0 or more characters that are not ',', ']' or ')' eg: '1.0-alpha'
#   ']'
# A Soft Requirement - eg: '1.0'
#   soft_requirement: 1 or more characters that are a-z, A-Z, 0-9, '.' or '-' eg: '1.0-alpha'


SPEC_REGEX = r"(?P<left_range>\[|\()(?P<lower_bound>[^,\]\)]*),(?P<upper_bound>[^\]\)]*)(?P<right_range>\]|\))|\[(?P<hard_requirement>[^,\]]*)\]|(?P<soft_requirement>[\w\.\-]+)"


class RangePredicate:
    """Represents a single testable range from a maven version spec.

    eg:
    (,1.0]:     x <= 1.0
    [1.2,1.3]:  1.2 <= x <= 1.3
    [1.0,2.0):  1.0 <= x < 2.0
    [1.5,):     x >= 1.5
    """

    def __init__(self, lower_bound, left_range, upper_bound, right_range):
        if lower_bound:
            self.lower_bound = MavenSemver(lower_bound)
        else:
            self.lower_bound = None
        self.left_range = left_range
        if upper_bound:
            self.upper_bound = MavenSemver(upper_bound)
        else:
            self.upper_bound = None
        self.right_range = right_range

    def __call__(self, version):
        if self.lower_bound is not None:
            if version < self.lower_bound:
                return False
            if self.left_range == "(" and version == self.lower_bound:
                return False

        if self.upper_bound is not None:
            if version > self.upper_bound:
                return False
            if self.right_range == ")" and version == self.upper_bound:
                return False
        return True


class MavenVersionSpec:
    """From https://maven.apache.org/pom.html#Dependency_Version_Requirement_Specification:

    Dependencies' version element define version requirements, used to compute effective dependency version.
    Version requirements have the following syntax:

    1.0:        "Soft" requirement on 1.0 (just a recommendation, if it matches all other ranges for the dependency)
    [1.0]:      "Hard" requirement on 1.0 - This does not imply that the only possible match is '1.0', the full version
                spec may contain disjoint elements eg: '[1.0],[1.2,4.0]' --> x == 1.0 or 1.2 <= x <= 4
    (,1.0]:     x <= 1.0
    [1.2,1.3]:  1.2 <= x <= 1.3
    [1.0,2.0):  1.0 <= x < 2.0
    [1.5,):     x >= 1.5
    (,1.0],[1.2,):    x <= 1.0 or x >= 1.2; multiple sets are comma-separated
    (,1.1),(1.1,):    this excludes 1.1 (for example if it is known not to work in combination with this library)
    """

    def __init__(self, version_spec):
        self.version_spec = version_spec
        self.hard_requirements = []
        self.soft_requirement = None
        self.only_soft_requirement = False
        self.specs = [match.groupdict() for match in re.finditer(SPEC_REGEX, version_spec)]
        self.range_predicates = []
        self.parse_spec(self.specs)

    def __repr__(self):
        return self.version_spec

    def parse_spec(self, specs):
        for spec in self.specs:
            if spec["hard_requirement"]:
                self.hard_requirements.append(MavenSemver(spec["hard_requirement"]))
            elif spec["soft_requirement"]:
                self.soft_requirement = MavenSemver(spec["soft_requirement"])
                if len(specs) == 1:
                    self.only_soft_requirement = True
            else:
                self.range_predicates.append(
                    RangePredicate(
                        lower_bound=spec["lower_bound"],
                        left_range=spec["left_range"],
                        upper_bound=spec["upper_bound"],
                        right_range=spec["right_range"],
                    )
                )

    def is_valid_version(self, version):
        def version_matches_range_predicate():
            return any(predicate(version) for predicate in self.range_predicates)

        if self.only_soft_requirement:
            return True
        return (
            version == self.soft_requirement or version in self.hard_requirements or version_matches_range_predicate()
        )

    def valid_versions(self, version_list):
        return [version for version in version_list if self.is_valid_version(version)]

    def preferred_version(self, versions):
        valid_versions = self.valid_versions(versions)
        if not valid_versions:
            return None
        if self.soft_requirement in valid_versions:
            return self.soft_requirement
        return max(valid_versions)
