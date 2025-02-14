# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import unittest

import pytest

from toolchain.satresolver.config import Config
from toolchain.satresolver.core import ResolutionError, Resolver
from toolchain.satresolver.dict_graph import DictGraph
from toolchain.satresolver.report import Line, Report
from toolchain.satresolver.test_helpers.core_test_data import Packages, PackageVersions


class ReportTest(unittest.TestCase):
    def test_simple(self):
        dependency_map = {
            Packages.AA: {PackageVersions.AA_100: [], PackageVersions.AA_200: []},
            Packages.AB: {PackageVersions.AB_100: [PackageVersions.AA_200]},
        }
        dependencies = {Packages.AA: {PackageVersions.AA_100}, Packages.AB: {PackageVersions.AB_100}}
        graph = DictGraph(transitive_dependency_map=dependency_map)
        config = Config(dependencies, graph)
        resolver = Resolver(config)
        with pytest.raises(
            ResolutionError, match="Could not resolve conflict for all versions of a:b depend on a:a:2.0.0"
        ):
            resolver.run()
        lines = Report(resolver.failure).construct_error_message()
        assert lines == [
            Line(
                message="Because all versions of a:b depend on a:a:2.0.0 and __ROOT__ depends on a:b, not a:a:2.0.0 is incompatible with __ROOT__",
                line_number=None,
            ),
            Line(message="So, because __ROOT__ depends on a:a:1.0.0, version solving failed.", line_number=None),
        ]

    def test_nested(self):
        dependency_map = {
            Packages.AA: {PackageVersions.AA_100: [], PackageVersions.AA_200: []},
            Packages.AB: {PackageVersions.AB_100: [PackageVersions.AA_200]},
            Packages.AC: {PackageVersions.AC_100: [PackageVersions.AB_100]},
        }
        graph = DictGraph(transitive_dependency_map=dependency_map)
        dependencies = {Packages.AA: {PackageVersions.AA_100}, Packages.AC: {PackageVersions.AC_100}}
        resolver = Resolver(config=Config(dependencies, graph))
        with pytest.raises(ResolutionError, match="Could not resolve conflict for all versions of a:c depend on a:b"):
            resolver.run()
        report = Report(resolver.failure)
        lines = report.construct_error_message()
        assert lines == [
            Line(
                message="Because all versions of a:c depend on a:b and all versions of a:b depend on a:a:2.0.0, a:c:Any is incompatible with not a:a:2.0.0",
                line_number=None,
            ),
            Line(
                message="And because __ROOT__ depends on a:c, not a:a:2.0.0 is incompatible with __ROOT__",
                line_number=None,
            ),
            Line(message="So, because __ROOT__ depends on a:a:1.0.0, version solving failed.", line_number=None),
        ]
