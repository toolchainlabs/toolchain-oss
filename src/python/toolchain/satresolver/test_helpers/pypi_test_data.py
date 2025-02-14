# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.lang.python.distributions.distribution_key import DistributionKey
from toolchain.lang.python.distributions.distribution_type import DistributionType
from toolchain.satresolver.pypi.platforms import Platform
from toolchain.satresolver.pypi.python_distribution import PythonPackageDistribution
from toolchain.satresolver.pypi.python_interpreter import PythonInterpreter
from toolchain.satresolver.pypi.tags import ALL_PLATFORM_TAGS
from toolchain.satresolver.pypi.term import PlatformConstraint, PythonInterpreterConstraint
from toolchain.satresolver.term import VersionConstraint
from toolchain.satresolver.test_helpers.pypi_utils import get_resolution_data

AAA = "aaa"
BBB = "bbb"
CCC = "ccc"
BADDEP = "bad-dependency"
BADINTERPRETER = "bad-interpreter"


class Distributions:
    aaa_100_whl_27 = PythonPackageDistribution.create(
        DistributionKey.create(
            filename="AAA-1.0.0-py27-none-any.whl",
            project_name=AAA,
            version="1.0.0",
            distribution_type=DistributionType.WHEEL,
            requires_python="python==2.7.6",
        ),
        get_resolution_data("AAA-1.0.0-py27-none-any.whl"),
    )

    aaa_100_whl_27_osx = PythonPackageDistribution.create(
        DistributionKey.create(
            filename="AAA-1.0.0-py27-none-macosx_10_9_x86_64.whl'",
            project_name=AAA,
            version="1.0.0",
            distribution_type=DistributionType.WHEEL,
            requires_python="python==2.7.6",
        ),
        get_resolution_data("AAA-1.0.0-py27-none-macosx_10_9_x86_64.whl"),
    )
    aaa_100_whl_27_win = PythonPackageDistribution.create(
        DistributionKey.create(
            filename="AAA-1.0.0-py27-none-win_amd64.whl'",
            project_name=AAA,
            version="1.0.0",
            distribution_type=DistributionType.WHEEL,
            requires_python="python==2.7.6",
        ),
        get_resolution_data("AAA-1.0.0-py27-none-win_amd64.whl"),
    )
    aaa_100_whl_33 = PythonPackageDistribution.create(
        DistributionKey.create(
            filename="AAA-1.0.0-py33-none-any.whl",
            project_name=AAA,
            version="1.0.0",
            distribution_type=DistributionType.WHEEL,
            requires_python="python>=3.3.",
        ),
        get_resolution_data("AAA-1.0.0-py33-none-any.whl"),
    )
    aaa_100_whl_33_abi3 = PythonPackageDistribution.create(
        DistributionKey.create(
            filename="AAA-1.0.0-py33-abi3-any.whl",
            project_name=AAA,
            version="1.0.0",
            distribution_type=DistributionType.WHEEL,
            requires_python="python>=3.3.",
        ),
        get_resolution_data("AAA-1.0.0-py33-none-any.whl"),
    )
    aaa_200_whl_33 = PythonPackageDistribution.create(
        DistributionKey.create(
            filename="AAA-2.0.0-py33-none-any.whl",
            project_name=AAA,
            version="2.0.0",
            distribution_type=DistributionType.WHEEL,
            requires_python="python>=3.3.",
        ),
        get_resolution_data("AAA-2.0.0-py33-none-any.whl"),
    )
    aaa_200_whl_33_abi3 = PythonPackageDistribution.create(
        DistributionKey.create(
            filename="AAA-2.0.0-py33-abi3-any.whl",
            project_name=AAA,
            version="2.0.0",
            distribution_type=DistributionType.WHEEL,
            requires_python="python>=3.3.",
        ),
        get_resolution_data("AAA-2.0.0-py33-abi3-any.whl"),
    )
    aaa_201_whl_33 = PythonPackageDistribution.create(
        DistributionKey.create(
            filename="AAA-2.0.1-py33-none-any.whl",
            project_name=AAA,
            version="2.0.1",
            distribution_type=DistributionType.WHEEL,
            requires_python="python>=3.3.",
        ),
        get_resolution_data("AAA-2.0.1-py33-none-any.whl"),
    )
    aaa_2012_whl_33 = PythonPackageDistribution.create(
        DistributionKey.create(
            filename="AAA-2.0.12-py33-none-any.whl",
            project_name=AAA,
            version="2.0.12",
            distribution_type=DistributionType.WHEEL,
            requires_python="python>=3.3.",
        ),
        get_resolution_data("AAA-2.0.12-py33-none-any.whl"),
    )
    bbb_100_whl_27 = PythonPackageDistribution.create(
        DistributionKey.create(
            filename="BBB-1.0.0-py27-none-any.whl",
            project_name=BBB,
            version="1.0.0",
            distribution_type=DistributionType.WHEEL,
            requires_python="python==2.7.6",
        ),
        get_resolution_data("BBB-1.0.0-py27-none-any.whl", "AAA==1.0.0"),
    )
    bbb_100_whl_33 = PythonPackageDistribution.create(
        DistributionKey.create(
            filename="BBB-1.0.0-py33-none-any.whl",
            project_name=BBB,
            version="1.0.0",
            distribution_type=DistributionType.WHEEL,
            requires_python="python==3.3.",
        ),
        get_resolution_data("BBB-1.0.0-py33-none-any.whl"),
    )
    bad_dep_100_whl_33 = PythonPackageDistribution.create(
        DistributionKey.create(
            filename="BAD_DEPENDENCY-1.0.0-py33-none-any.whl",
            project_name=BADDEP,
            version="1.0.0",
            distribution_type=DistributionType.WHEEL,
            requires_python="python>=3.3",
        ),
        get_resolution_data("BAD_DEPENDENCY-1.0.0-py33-none-any.whl", "AAA==1.0,"),
    )
    bad_interpreter_100_whl_33 = PythonPackageDistribution.create(
        DistributionKey.create(
            filename="BAD_INTERPRETER-1.0.0-py33-none-any.whl",
            project_name=BADINTERPRETER,
            version="1.0.0",
            distribution_type=DistributionType.WHEEL,
            requires_python="python>=3.3,",
        ),
        get_resolution_data("BAD_INTERPRETER-1.0.0-py33-none-any.whl", "AAA==1.0,"),
    )
    ccc_100_whl_33 = PythonPackageDistribution.create(
        DistributionKey.create(
            filename="CCC-1.0.0-py33-none-any.whl",
            project_name=CCC,
            version="1.0.0",
            distribution_type=DistributionType.WHEEL,
            requires_python="python==3.3.",
        ),
        get_resolution_data("CCC-1.0.0-py33-none-any.whl", "AAA==1.0"),
    )
    core_schema_whl_2 = PythonPackageDistribution.create(
        DistributionKey.create(
            filename="coreschema-0.0.4-py2-none-any.whl",
            project_name="coreschema",
            version="0.0.4",
            distribution_type=DistributionType.WHEEL,
            requires_python="python~=2",
        ),
        get_resolution_data("coreschema-0.0.4-py2-none-any.whl", "jinja"),
    )
    core_schema_whl_3 = PythonPackageDistribution.create(
        DistributionKey.create(
            filename="coreschema-0.3.22-py3-none-any.whl",
            project_name="coreschema",
            version="0.3.22",
            distribution_type=DistributionType.WHEEL,
            requires_python="python==3.3",
        ),
        get_resolution_data("coreschema-0.3.22-py3-none-any.whl", "jinja"),
    )
    duplicate_deps_100_whl_33 = PythonPackageDistribution(
        DistributionKey.create(
            filename="duplicatedeps-1.0.0-py3-none-any.whl",
            project_name="duplicatedeps",
            version="1.0.0",
            distribution_type=DistributionType.WHEEL,
            requires_python="python==3.3",
        ),
        get_resolution_data("duplicatedeps-1.0.0-py3-none-any.whl", "AAA>=2.0.0", "AAA<=1.0.0"),
    )


class DistributionsSet:
    dist_set_1 = [
        Distributions.aaa_100_whl_27,
        Distributions.aaa_100_whl_27_osx,
        Distributions.aaa_100_whl_27_win,
        Distributions.aaa_100_whl_33,
        Distributions.aaa_100_whl_33_abi3,
        Distributions.aaa_200_whl_33,
        Distributions.core_schema_whl_2,
        Distributions.core_schema_whl_3,
    ]
    dist_set_2 = [
        Distributions.aaa_100_whl_27,
        Distributions.aaa_200_whl_33,
        Distributions.core_schema_whl_2,
    ]


class VersionConstraints:
    requires_aaa_100 = VersionConstraint.require(
        package_name=AAA,
        versions={
            Distributions.aaa_100_whl_27,
            Distributions.aaa_100_whl_27_osx,
            Distributions.aaa_100_whl_27_win,
            Distributions.aaa_100_whl_33,
        },
        all_versions={
            Distributions.aaa_100_whl_27,
            Distributions.aaa_100_whl_27_osx,
            Distributions.aaa_100_whl_27_win,
            Distributions.aaa_100_whl_33,
            Distributions.aaa_200_whl_33,
        },
    )
    requires_aaa_200 = VersionConstraint.require(
        package_name=AAA,
        versions={Distributions.aaa_200_whl_33},
        all_versions={
            Distributions.aaa_100_whl_27,
            Distributions.aaa_100_whl_27_osx,
            Distributions.aaa_100_whl_27_win,
            Distributions.aaa_100_whl_33,
            Distributions.aaa_200_whl_33,
        },
    )
    requires_bbb_100 = VersionConstraint.require(
        package_name=BBB,
        versions={Distributions.bbb_100_whl_27, Distributions.bbb_100_whl_33},
        all_versions={Distributions.bbb_100_whl_27, Distributions.bbb_100_whl_33},
    )
    excludes_bbb_100 = VersionConstraint.exclude(
        package_name=BBB,
        versions={Distributions.bbb_100_whl_27, Distributions.bbb_100_whl_33},
        all_versions={Distributions.bbb_100_whl_27, Distributions.bbb_100_whl_33},
    )


class Interpreters:
    python_276 = PythonInterpreter(interpreter="python", version="2.7.6")
    python_372 = PythonInterpreter(interpreter="python", version="3.7.2")
    python_33 = PythonInterpreter(interpreter="python", version="3.3")
    python_24 = PythonInterpreter(interpreter="python", version="2.4")
    all_python_interpreters = {python_24, python_276, python_33, python_372}


class InterpreterConstraints:
    requires_python = PythonInterpreterConstraint.require(
        versions=Interpreters.all_python_interpreters, all_versions=Interpreters.all_python_interpreters
    )
    requires_python_2 = PythonInterpreterConstraint.require(
        versions={Interpreters.python_276, Interpreters.python_24}, all_versions=Interpreters.all_python_interpreters
    )
    requires_python_3 = PythonInterpreterConstraint.require(
        versions={Interpreters.python_33, Interpreters.python_372}, all_versions=Interpreters.all_python_interpreters
    )
    excludes_python = PythonInterpreterConstraint.exclude(
        versions=Interpreters.all_python_interpreters, all_versions=Interpreters.all_python_interpreters
    )
    excludes_python_2 = PythonInterpreterConstraint.exclude(
        versions={Interpreters.python_276, Interpreters.python_24}, all_versions=Interpreters.all_python_interpreters
    )
    excludes_python_3 = PythonInterpreterConstraint.exclude(
        versions={Interpreters.python_33, Interpreters.python_372}, all_versions=Interpreters.all_python_interpreters
    )


ALL_PLATFORMS = {Platform(platform=platform) for platform in ALL_PLATFORM_TAGS}


class PlatformConstraints:
    requires_linux_x86_64 = PlatformConstraint.require(
        platform=Platform("linux_x86_64"), versions={Platform("linux_x86_64")}, all_versions=ALL_PLATFORMS
    )
    requires_any = PlatformConstraint.require(
        platform=Platform("any"), versions=ALL_PLATFORMS, all_versions=ALL_PLATFORMS
    )
    requires_macosx_10_10_intel = PlatformConstraint.require(
        platform=Platform("macosx_10_10_intel"), versions={Platform("macosx_10_10_intel")}, all_versions=ALL_PLATFORMS
    )
    excludes_linux_x86_64 = PlatformConstraint.exclude(
        platform=Platform("linux_x86_64"), versions={Platform("linux_x86_64")}, all_versions=ALL_PLATFORMS
    )
    excludes_any = PlatformConstraint.exclude(
        platform=Platform("any"), versions=ALL_PLATFORMS, all_versions=ALL_PLATFORMS
    )
    excludes_macosx_10_10_intel = PlatformConstraint.exclude(
        platform=Platform("macosx_10_10_intel"), versions={Platform("macosx_10_10_intel")}, all_versions=ALL_PLATFORMS
    )
