# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.satresolver.config import Config
from toolchain.satresolver.dict_graph import DictGraph
from toolchain.satresolver.package import PackageVersion


class Packages:
    AA = "a:a"
    AB = "a:b"
    AC = "a:c"
    BA = "b:a"
    BB = "b:b"
    BC = "b:c"


# PACKAGE VERSIONS
class PackageVersions:
    AA_100 = PackageVersion(Packages.AA, "1.0.0")
    AA_200 = PackageVersion(Packages.AA, "2.0.0")
    AA_300 = PackageVersion(Packages.AA, "3.0.0")
    AA_400 = PackageVersion(Packages.AA, "4.0.0")
    AB_100 = PackageVersion(Packages.AB, "1.0.0")
    AB_200 = PackageVersion(Packages.AB, "2.0.0")
    AB_300 = PackageVersion(Packages.AB, "3.0.0")
    AC_100 = PackageVersion(Packages.AC, "1.0.0")
    AC_200 = PackageVersion(Packages.AC, "2.0.0")
    AC_300 = PackageVersion(Packages.AC, "3.0.0")
    BA_100 = PackageVersion(Packages.BA, "1.0.0")
    BA_200 = PackageVersion(Packages.BA, "2.0.0")
    BB_100 = PackageVersion(Packages.BB, "1.0.0")
    BB_200 = PackageVersion(Packages.BB, "2.0.0")
    BC_100 = PackageVersion(Packages.BC, "1.0.0")
    BC_200 = PackageVersion(Packages.BC, "2.0.0")


SIMPLE_DEPENDENCY_MAP = {
    Packages.AA: {
        PackageVersions.AA_100: [
            PackageVersions.AB_100,
            PackageVersions.AB_200,
            PackageVersions.AC_100,
            PackageVersions.AC_200,
        ],
        PackageVersions.AA_200: [
            PackageVersions.AB_100,
            PackageVersions.AB_200,
            PackageVersions.AB_300,
            PackageVersions.AC_100,
            PackageVersions.AC_200,
        ],
        PackageVersions.AA_300: [
            PackageVersions.AB_100,
            PackageVersions.AB_200,
            PackageVersions.AB_300,
            PackageVersions.AC_100,
            PackageVersions.AC_200,
            PackageVersions.AC_300,
        ],
        PackageVersions.AA_400: [
            PackageVersions.AB_100,
            PackageVersions.AB_200,
            PackageVersions.AB_300,
            PackageVersions.AC_100,
            PackageVersions.AC_200,
            PackageVersions.AC_300,
        ],
    },
    Packages.AB: {PackageVersions.AB_100: [], PackageVersions.AB_200: [], PackageVersions.AB_300: []},
    Packages.AC: {PackageVersions.AC_100: [], PackageVersions.AC_200: [], PackageVersions.AC_300: []},
}


SHARED_DEPENDENCY_MAP = {
    Packages.AA: {
        PackageVersions.AA_100: [
            PackageVersions.AB_100,
            PackageVersions.AB_200,
            PackageVersions.AC_100,
            PackageVersions.AC_200,
        ],
        PackageVersions.AA_200: [
            PackageVersions.AB_100,
            PackageVersions.AB_200,
            PackageVersions.AB_300,
            PackageVersions.AC_100,
            PackageVersions.AC_200,
        ],
        PackageVersions.AA_300: [
            PackageVersions.AB_100,
            PackageVersions.AB_200,
            PackageVersions.AB_300,
            PackageVersions.AC_100,
            PackageVersions.AC_200,
            PackageVersions.AC_300,
        ],
        PackageVersions.AA_400: [
            PackageVersions.AB_100,
            PackageVersions.AB_200,
            PackageVersions.AB_300,
            PackageVersions.AC_100,
            PackageVersions.AC_200,
            PackageVersions.AC_300,
        ],
    },
    Packages.AB: {PackageVersions.AB_100: [], PackageVersions.AB_200: [], PackageVersions.AB_300: []},
    Packages.AC: {
        PackageVersions.AC_100: [PackageVersions.AB_100, PackageVersions.AB_200, PackageVersions.AB_300],
        PackageVersions.AC_200: [PackageVersions.AB_100, PackageVersions.AB_200, PackageVersions.AB_300],
        PackageVersions.AC_300: [PackageVersions.AB_100, PackageVersions.AB_200, PackageVersions.AB_300],
    },
}


ROOT_DEPS_FOR_EXAMPLES = {
    "simple": {Packages.AA: {PackageVersions.AA_300, PackageVersions.AA_400}},
    "shared": {
        Packages.AA: {PackageVersions.AA_300, PackageVersions.AA_400},
        Packages.AC: {PackageVersions.AC_100, PackageVersions.AC_200},
    },
}


DEPENDENCIES_FOR_EXAMPLES = {"simple": SIMPLE_DEPENDENCY_MAP, "shared": SHARED_DEPENDENCY_MAP}


def demo_config(example):
    root_deps = ROOT_DEPS_FOR_EXAMPLES[example]
    dependency_map = DEPENDENCIES_FOR_EXAMPLES[example]
    config = Config(dependencies=root_deps, graph=DictGraph(transitive_dependency_map=dependency_map))
    return config
