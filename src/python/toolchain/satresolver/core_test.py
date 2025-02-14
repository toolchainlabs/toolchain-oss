# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.satresolver.assignment import Assignment
from toolchain.satresolver.cause import ConflictCause, DependencyCause, IncompatibilityCause, PackageNotFoundCause
from toolchain.satresolver.config import Config
from toolchain.satresolver.core import ResolutionError, Resolver
from toolchain.satresolver.dict_graph import DictGraph
from toolchain.satresolver.incompatibility import Incompatibility
from toolchain.satresolver.package import ROOT
from toolchain.satresolver.test_helpers.core_test_data import Packages, PackageVersions, Terms

# INCOMPATIBILITIES
AA_100_DEPENDS_ON_AB_100 = Incompatibility(cause=DependencyCause(), terms=[Terms.TERM_AA_100, Terms.TERM_NOT_AB_100])
AA_100_DEPENDS_ON_AB_200 = Incompatibility(cause=DependencyCause(), terms=[Terms.TERM_AA_100, Terms.TERM_NOT_AB_200])
AA_200_DEPENDS_ON_AB_200 = Incompatibility(cause=DependencyCause(), terms=[Terms.TERM_AA_200, Terms.TERM_NOT_AB_200])
AA_100_DEPENDS_ON_BB_100 = Incompatibility(cause=DependencyCause(), terms=[Terms.TERM_AA_100, Terms.TERM_NOT_BB_100])
AA_100_DEPENDS_ON_BC_200 = Incompatibility(cause=DependencyCause(), terms=[Terms.TERM_AA_100, Terms.TERM_NOT_BC_200])
BA_100_DEPENDS_ON_BC_200 = Incompatibility(cause=DependencyCause(), terms=[Terms.TERM_BA_100, Terms.TERM_NOT_BC_200])
BB_100_DEPENDS_ON_AB_100 = Incompatibility(cause=DependencyCause(), terms=[Terms.TERM_BB_100, Terms.TERM_NOT_AB_100])


def create_resolver(transitive_dependency_map, dependencies, locked=None, use_latest=None, downgrades=None):
    config = Config(
        dependencies=dependencies,
        graph=DictGraph(transitive_dependency_map),
        use_latest=use_latest,
        locked=locked,
        downgrades=downgrades,
    )
    return Resolver(config)


class TestCore:
    @pytest.fixture()
    def resolver(self):
        return create_resolver(transitive_dependency_map={}, dependencies={})

    def test_setup_root(self):
        resolver = create_resolver(
            transitive_dependency_map={Packages.AA: {PackageVersions.AA_100: []}},
            dependencies={Packages.AA: {PackageVersions.AA_100}},
        )
        resolver._setup_root()
        assert resolver._solution._decisions == {ROOT.package_name: Terms.TERM_ROOT}
        assert set(resolver._incompatibilities.keys()) == {ROOT.package_name, Packages.AA}

    def test_add_incompatibility(self, resolver):
        resolver._add_incompatibility(AA_100_DEPENDS_ON_AB_100)
        assert sorted(resolver._incompatibilities.keys()) == [Packages.AA, Packages.AB]

    def test_propagate_incompatibility(self, resolver):
        resolver._solution._terms = {Packages.AA: Terms.TERM_AA_100, Packages.BC: Terms.TERM_BC_100}
        # Incompatible - Solution includes PackageVersions.AA_100
        assert resolver._propagate_incompatibility(AA_200_DEPENDS_ON_AB_200) is None
        # Inconclusive - solution has no details for BB or AB
        assert resolver._propagate_incompatibility(BB_100_DEPENDS_ON_AB_100) is None
        # Conflict - solution includes PackageVersions.AA_100 and excludes PackageVersions.BC_200
        assert resolver._propagate_incompatibility(AA_100_DEPENDS_ON_BC_200) == AA_100_DEPENDS_ON_BC_200
        # Can derive new info - solution includes PackageVersions.AA_100 and has no details for BB
        assert resolver._propagate_incompatibility(AA_100_DEPENDS_ON_BB_100) == Packages.BB

    def test_sort_incompatibility_terms_by_most_recently_satisfied(self, resolver):
        resolver._solution.decide(Terms.TERM_AA_100)
        resolver._solution.decide(Terms.TERM_NOT_AB_100)
        sorted_terms = resolver._sort_incompatibility_terms_by_most_recently_satisfied(AA_100_DEPENDS_ON_AB_100)
        assert sorted_terms[0][0] == Terms.TERM_AA_100
        assert sorted_terms[1][0] == Terms.TERM_NOT_AB_100

    def test_previous_decision_level(self):
        dependency_map = {
            Packages.AA: {PackageVersions.AA_100: [], PackageVersions.AA_200: [PackageVersions.AB_200]},
            Packages.AB: {PackageVersions.AB_100: [], PackageVersions.AB_200: []},
            Packages.AC: {PackageVersions.AC_100: [PackageVersions.AB_100]},
        }
        resolver = create_resolver(
            transitive_dependency_map=dependency_map,
            dependencies={
                Packages.AA: {PackageVersions.AA_100, PackageVersions.AA_200},
                Packages.AC: {PackageVersions.AC_100},
            },
        )
        resolver.run()
        sorted_terms = resolver._sort_incompatibility_terms_by_most_recently_satisfied(AA_100_DEPENDS_ON_AB_200)
        assert resolver._previous_decision_level(sorted_terms) == 2

    def test_merge_terms(self, resolver):
        terms = [Terms.TERM_AA_100, Terms.TERM_AA_12, Terms.TERM_NOT_AB_100]
        merged_terms = set(resolver._merge_terms(terms))
        assert merged_terms == {Terms.TERM_AA_100, Terms.TERM_NOT_AB_100}
        with pytest.raises(ValueError, match="BUG: Mutually exclusive terms in incompatibility: a:a:1.0.0, a:a:2.0.0"):
            resolver._merge_terms([Terms.TERM_AA_100, Terms.TERM_AA_200])

    def test_create_incompatibility_from_conflict(self, resolver):
        incompatibility = AA_100_DEPENDS_ON_AB_200
        most_recent_term = Terms.TERM_NOT_AB_200
        most_recent_satisfier = Assignment(
            term=Terms.TERM_AB_100, decision_level=2, index=2, cause=IncompatibilityCause(BB_100_DEPENDS_ON_AB_100)
        )
        new_incompatibility = resolver._create_incompatibility_from_conflict(
            incompatibility=incompatibility,
            most_recent_term=most_recent_term,
            most_recent_satisfier=most_recent_satisfier,
        )
        assert set(new_incompatibility.terms) == {Terms.TERM_AA_100, Terms.TERM_BB_100}
        assert new_incompatibility.cause.__class__ == ConflictCause

    def test_resolve_conflict(self):
        dependency_map = {
            Packages.AA: {PackageVersions.AA_100: [], PackageVersions.AA_200: []},
            Packages.AB: {PackageVersions.AB_100: [], PackageVersions.AB_200: []},
            Packages.BA: {PackageVersions.BA_100: [PackageVersions.AB_100]},
            Packages.BC: {PackageVersions.BC_100: [], PackageVersions.BC_200: []},
        }
        dependencies = {
            Packages.AA: {PackageVersions.AA_100, PackageVersions.AA_200},
            Packages.BA: {PackageVersions.BA_100},
            Packages.BC: {PackageVersions.BC_100},
        }
        resolver = create_resolver(transitive_dependency_map=dependency_map, dependencies=dependencies)
        resolver.run()
        assert resolver._resolve_conflict(AA_200_DEPENDS_ON_AB_200) == AA_200_DEPENDS_ON_AB_200
        with pytest.raises(
            ResolutionError, match="Could not resolve conflict for b:a:1.0.0 depends on b:c:2.0.0"
        ) as error_info:
            resolver._resolve_conflict(BA_100_DEPENDS_ON_BC_200)
        error_message_lines = error_info.value.get_failure_error_message().splitlines()
        assert len(error_message_lines) == 2
        assert error_message_lines == [
            "Because b:a:1.0.0 depends on b:c:2.0.0 and __ROOT__ depends on b:c:1.0.0, b:a:1.0.0 is incompatible with __ROOT__",
            "So, because __ROOT__ depends on b:a, version solving failed.",
        ]

    def test_is_conflict(self):
        dependency_map = {
            Packages.AA: {PackageVersions.AA_100: [], PackageVersions.AA_200: []},
            Packages.AB: {PackageVersions.AB_100: [], PackageVersions.AB_200: []},
            Packages.BA: {PackageVersions.BA_100: [PackageVersions.AB_100]},
        }
        dependencies = {
            Packages.AA: {PackageVersions.AA_100, PackageVersions.AA_200},
            Packages.BA: {PackageVersions.BA_100},
        }
        resolver = create_resolver(transitive_dependency_map=dependency_map, dependencies=dependencies)
        # Solution: PackageVersions.AA_200, PackageVersions.AB_100, PackageVersions.BA_100
        resolver.run()
        assert resolver._is_conflict(AA_200_DEPENDS_ON_AB_200) is True
        assert resolver._is_conflict(AA_100_DEPENDS_ON_AB_200) is False

    def test_choose_package_version(self):
        resolver = create_resolver(
            transitive_dependency_map={Packages.AA: {PackageVersions.AA_100: [], PackageVersions.AA_200: []}},
            dependencies={Packages.AA: {PackageVersions.AA_100}},
        )
        resolver._solution._terms = {Packages.AA: Terms.TERM_AA_100}
        assert resolver._choose_package_version() == Packages.AA
        resolver._solution.decide(Terms.TERM_AA_100)
        assert resolver._choose_package_version() is None
        # BB is not in the transitive dependency map.
        resolver._solution._terms = {Packages.BB: Terms.TERM_BB_100}
        assert Packages.BB == resolver._choose_package_version()
        incompatibilities = resolver._incompatibilities[Packages.BB]
        assert isinstance(incompatibilities[0].cause, PackageNotFoundCause)

    def test_no_dependencies(self, resolver):
        assert resolver.run() == []

    def test_simple_dependency_tree(self):
        dependency_map = {
            Packages.AA: {PackageVersions.AA_200: [PackageVersions.AB_200]},
            Packages.AB: {PackageVersions.AB_100: [], PackageVersions.AB_200: [PackageVersions.AC_100]},
            Packages.AC: {PackageVersions.AC_100: []},
            Packages.BA: {
                PackageVersions.BA_100: [
                    PackageVersions.BB_100,
                    PackageVersions.BB_200,
                    PackageVersions.BC_100,
                    PackageVersions.BC_200,
                ]
            },
            Packages.BB: {PackageVersions.BB_100: [], PackageVersions.BB_200: []},
            Packages.BC: {PackageVersions.BC_100: [], PackageVersions.BC_200: []},
        }
        resolver = create_resolver(
            transitive_dependency_map=dependency_map,
            dependencies={Packages.AA: {PackageVersions.AA_200}, Packages.BA: {PackageVersions.BA_100}},
        )
        result = resolver.run()
        assert result == [
            PackageVersions.AA_200,
            PackageVersions.AB_200,
            PackageVersions.AC_100,
            PackageVersions.BA_100,
            PackageVersions.BB_200,
            PackageVersions.BC_200,
        ]

    def test_bad_dep(self):
        dependency_map = {Packages.AA: {PackageVersions.AA_100: [], PackageVersions.AA_200: [PackageVersions.AB_100]}}
        resolver = create_resolver(
            transitive_dependency_map=dependency_map, dependencies={Packages.AA: {PackageVersions.AA_200}}
        )
        with pytest.raises(ResolutionError, match="Could not resolve conflict for a:a:2.0.0 depends on a:b:1.0.0"):
            result = resolver.run()

        # With Bad but solvable dep
        resolver = create_resolver(
            transitive_dependency_map=dependency_map,
            dependencies={Packages.AA: {PackageVersions.AA_100, PackageVersions.AA_200}},
        )
        result = resolver.run()
        assert resolver._solution._attempted_solutions == 2
        assert result == [PackageVersions.AA_100]

    def test_shared_dependency_with_overlapping_constraints(self):
        dependency_map = {
            Packages.AA: {
                PackageVersions.AA_100: [],
                PackageVersions.AA_200: [],
                PackageVersions.AA_300: [],
                PackageVersions.AA_400: [],
            },
            Packages.AB: {
                PackageVersions.AB_100: [PackageVersions.AA_100, PackageVersions.AA_200, PackageVersions.AA_300]
            },
            Packages.AC: {PackageVersions.AC_100: [PackageVersions.AA_300, PackageVersions.AA_400]},
        }
        resolver = create_resolver(
            transitive_dependency_map=dependency_map,
            dependencies={Packages.AB: {PackageVersions.AB_100}, Packages.AC: {PackageVersions.AC_100}},
        )
        result = resolver.run()
        assert result == [PackageVersions.AA_300, PackageVersions.AB_100, PackageVersions.AC_100]

    def test_shared_dependency_with_transitive_effects(self):
        dependency_map = {
            Packages.AA: {
                PackageVersions.AA_100: [],
                PackageVersions.AA_200: [],
                PackageVersions.AA_300: [],
                PackageVersions.AA_400: [],
            },
            Packages.AB: {
                PackageVersions.AB_100: [PackageVersions.AA_100, PackageVersions.AA_200, PackageVersions.AA_300],
                PackageVersions.AB_200: [PackageVersions.AA_100, PackageVersions.AA_200],
            },
            Packages.AC: {PackageVersions.AC_100: [PackageVersions.AA_300, PackageVersions.AA_400]},
        }
        resolver = create_resolver(
            transitive_dependency_map=dependency_map,
            dependencies={
                Packages.AB: {PackageVersions.AB_100, PackageVersions.AB_200},
                Packages.AC: {PackageVersions.AC_100},
            },
        )
        result = resolver.run()
        assert result == [PackageVersions.AA_300, PackageVersions.AB_100, PackageVersions.AC_100]

    def test_circular_dependency(self):
        dependency_map = {
            Packages.AA: {PackageVersions.AA_100: [PackageVersions.AB_100]},
            Packages.AB: {PackageVersions.AB_100: [PackageVersions.AA_100]},
        }
        resolver = create_resolver(
            transitive_dependency_map=dependency_map, dependencies={Packages.AA: {PackageVersions.AA_100}}
        )
        result = resolver.run()
        assert result == [PackageVersions.AA_100, PackageVersions.AB_100]

    def test_removes_dependency(self):
        dependency_map = {
            Packages.AA: {PackageVersions.AA_100: []},
            Packages.AB: {PackageVersions.AB_100: [PackageVersions.AA_200]},
            Packages.AC: {PackageVersions.AC_100: [], PackageVersions.AC_200: [PackageVersions.AB_100]},
        }
        resolver = create_resolver(
            transitive_dependency_map=dependency_map,
            dependencies={
                Packages.AA: {PackageVersions.AA_100},
                Packages.AC: {PackageVersions.AC_100, PackageVersions.AC_200},
            },
        )
        result = resolver.run()
        assert resolver._solution._attempted_solutions == 2
        assert result == [PackageVersions.AA_100, PackageVersions.AC_100]

    def test_no_valid_solution(self):
        dependency_map = {
            Packages.AA: {PackageVersions.AA_100: [], PackageVersions.AA_200: []},
            Packages.AB: {PackageVersions.AB_100: [PackageVersions.AA_200]},
        }
        resolver = create_resolver(
            transitive_dependency_map=dependency_map,
            dependencies={Packages.AA: {PackageVersions.AA_100}, Packages.AB: {PackageVersions.AB_100}},
        )
        with pytest.raises(
            ResolutionError, match="Could not resolve conflict for all versions of a:b depend on a:a:2.0.0"
        ) as error_info:
            resolver.run()
        assert error_info.value.to_dict() == {
            "msg": "Because all versions of a:b depend on a:a:2.0.0 and __ROOT__ depends on a:b, not a:a:2.0.0 is incompatible with __ROOT__\n"
            "So, because __ROOT__ depends on a:a:1.0.0, version solving failed."
        }

    def test_get_dependency_edges_for_result(self):
        dependency_map = {
            Packages.AA: {PackageVersions.AA_200: []},
            Packages.AB: {PackageVersions.AB_100: [PackageVersions.AA_200]},
            Packages.AC: {PackageVersions.AC_200: [PackageVersions.AB_100]},
            Packages.BA: {PackageVersions.BA_100: [PackageVersions.AB_100, PackageVersions.AC_200]},
        }
        resolver = create_resolver(
            transitive_dependency_map=dependency_map, dependencies={Packages.BA: {PackageVersions.BA_100}}
        )
        resolver.run()
        edges = resolver.get_dependency_edges_for_result()
        assert [
            (Packages.AB, Packages.AA),
            (Packages.AC, Packages.AB),
            (Packages.BA, Packages.AB),
            (Packages.BA, Packages.AC),
        ] == sorted(edges)
