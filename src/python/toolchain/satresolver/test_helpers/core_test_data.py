# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.satresolver.package import PackageVersion
from toolchain.satresolver.term import RootConstraint, VersionConstraint


class Packages:
    AA = "a:a"
    AB = "a:b"
    AC = "a:c"
    BA = "b:a"
    BB = "b:b"
    BC = "b:c"


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


class Groups:
    AA_ALL = {PackageVersions.AA_100, PackageVersions.AA_200, PackageVersions.AA_300, PackageVersions.AA_400}
    AB_ALL = {PackageVersions.AB_100, PackageVersions.AB_200, PackageVersions.AB_300}
    AC_ALL = {PackageVersions.AC_100, PackageVersions.AC_200, PackageVersions.AC_300}
    BA_ALL = {PackageVersions.BA_100, PackageVersions.BA_200}
    BB_ALL = {PackageVersions.BB_100, PackageVersions.BB_200}
    BC_ALL = {PackageVersions.BC_100, PackageVersions.BC_200}


class Terms:
    TERM_ROOT = RootConstraint.require()

    TERM_AA_100 = VersionConstraint.require(
        package_name=Packages.AA, versions={PackageVersions.AA_100}, all_versions=Groups.AA_ALL
    )
    TERM_AA_200 = VersionConstraint.require(
        package_name=Packages.AA, versions={PackageVersions.AA_200}, all_versions=Groups.AA_ALL
    )
    TERM_AA_300 = VersionConstraint.require(
        package_name=Packages.AA, versions={PackageVersions.AA_300}, all_versions=Groups.AA_ALL
    )
    TERM_AA_400 = VersionConstraint.require(
        package_name=Packages.AA, versions={PackageVersions.AA_400}, all_versions=Groups.AA_ALL
    )
    TERM_AA_12 = VersionConstraint.require(
        package_name=Packages.AA, versions={PackageVersions.AA_100, PackageVersions.AA_200}, all_versions=Groups.AA_ALL
    )
    TERM_AA_234 = VersionConstraint.require(
        package_name=Packages.AA,
        versions={PackageVersions.AA_200, PackageVersions.AA_300, PackageVersions.AA_400},
        all_versions=Groups.AA_ALL,
    )
    TERM_AA_34 = VersionConstraint.require(
        package_name=Packages.AA, versions={PackageVersions.AA_300, PackageVersions.AA_400}, all_versions=Groups.AA_ALL
    )
    TERM_AA_ALL = VersionConstraint.require(
        package_name=Packages.AA, versions=Groups.AA_ALL, all_versions=Groups.AA_ALL
    )

    TERM_NOT_AA_100 = VersionConstraint.exclude(
        package_name=Packages.AA, versions={PackageVersions.AA_100}, all_versions=Groups.AA_ALL
    )
    TERM_NOT_AA_200 = VersionConstraint.exclude(
        package_name=Packages.AA, versions={PackageVersions.AA_200}, all_versions=Groups.AA_ALL
    )
    TERM_NOT_AA_300 = VersionConstraint.exclude(
        package_name=Packages.AA, versions={PackageVersions.AA_300}, all_versions=Groups.AA_ALL
    )
    TERM_NOT_AA_12 = VersionConstraint.exclude(
        package_name=Packages.AA, versions={PackageVersions.AA_100, PackageVersions.AA_200}, all_versions=Groups.AA_ALL
    )
    TERM_NOT_AA_234 = VersionConstraint.exclude(
        package_name=Packages.AA,
        versions={PackageVersions.AA_200, PackageVersions.AA_300, PackageVersions.AA_400},
        all_versions=Groups.AA_ALL,
    )
    TERM_NOT_AA_ALL = VersionConstraint.exclude(
        package_name=Packages.AA, versions=Groups.AA_ALL, all_versions=Groups.AA_ALL
    )

    TERM_AB_100 = VersionConstraint.require(
        package_name=Packages.AB, versions={PackageVersions.AB_100}, all_versions=Groups.AB_ALL
    )
    TERM_AB_200 = VersionConstraint.require(
        package_name=Packages.AB, versions={PackageVersions.AB_200}, all_versions=Groups.AB_ALL
    )
    TERM_AB_ALL = VersionConstraint.require(
        package_name=Packages.AB, versions=Groups.AB_ALL, all_versions=Groups.AB_ALL
    )

    TERM_NOT_AB_100 = VersionConstraint.exclude(
        package_name=Packages.AB, versions={PackageVersions.AB_100}, all_versions=Groups.AB_ALL
    )
    TERM_NOT_AB_200 = VersionConstraint.exclude(
        package_name=Packages.AB, versions={PackageVersions.AB_200}, all_versions=Groups.AB_ALL
    )
    TERM_NOT_AB_ALL = VersionConstraint.exclude(
        package_name=Packages.AB, versions=Groups.AB_ALL, all_versions=Groups.AB_ALL
    )

    TERM_AC_100 = VersionConstraint.require(
        package_name=Packages.AC, versions={PackageVersions.AC_100}, all_versions=Groups.AC_ALL
    )
    TERM_AC_200 = VersionConstraint.require(
        package_name=Packages.AC, versions={PackageVersions.AC_200}, all_versions=Groups.AC_ALL
    )
    TERM_AC_ALL = VersionConstraint.require(
        package_name=Packages.AC, versions=Groups.AC_ALL, all_versions=Groups.AC_ALL
    )

    TERM_BA_100 = VersionConstraint.require(
        package_name=Packages.BA, versions={PackageVersions.BA_100}, all_versions=Groups.BA_ALL
    )
    TERM_BA_200 = VersionConstraint.require(
        package_name=Packages.BA, versions={PackageVersions.BA_200}, all_versions=Groups.BA_ALL
    )
    TERM_BA_ALL = VersionConstraint.require(
        package_name=Packages.BA, versions=Groups.BA_ALL, all_versions=Groups.BA_ALL
    )

    TERM_BB_100 = VersionConstraint.require(
        package_name=Packages.BB, versions={PackageVersions.BB_100}, all_versions=Groups.BB_ALL
    )
    TERM_BB_ALL = VersionConstraint.require(
        package_name=Packages.BB, versions=Groups.BB_ALL, all_versions=Groups.BB_ALL
    )

    TERM_NOT_BB_100 = VersionConstraint.exclude(
        package_name=Packages.BB, versions={PackageVersions.BB_100}, all_versions=Groups.BB_ALL
    )
    TERM_NOT_BB_ALL = VersionConstraint.exclude(
        package_name=Packages.BB, versions=Groups.BB_ALL, all_versions=Groups.BB_ALL
    )

    TERM_BC_100 = VersionConstraint.require(
        package_name=Packages.BC, versions={PackageVersions.BC_100}, all_versions=Groups.BC_ALL
    )

    TERM_NOT_BC_200 = VersionConstraint.exclude(
        package_name=Packages.BC, versions={PackageVersions.BC_200}, all_versions=Groups.BC_ALL
    )
