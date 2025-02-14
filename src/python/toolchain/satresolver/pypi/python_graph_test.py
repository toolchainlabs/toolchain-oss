# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from pathlib import Path

import pkg_resources
import pytest

from toolchain.satresolver.core import ResolutionError, Resolver
from toolchain.satresolver.graph import InvalidRequirementsError, PackageNotFoundError, VersionNotFoundError
from toolchain.satresolver.pypi.depgraph import Depgraph
from toolchain.satresolver.pypi.python_config import PythonConfig
from toolchain.satresolver.pypi.python_distribution import PythonPackageDistribution
from toolchain.satresolver.pypi.python_graph import PythonGraph, get_supported_platform_tags, should_include
from toolchain.satresolver.test_helpers.pypi_test_data import AAA, BBB, Distributions, Interpreters
from toolchain.satresolver.test_helpers.pypi_utils import create_fake_depgraph

BAD = "bad"


@pytest.fixture()
def fake_depgraph_dataset(tmp_path: Path) -> Depgraph:
    return create_fake_depgraph(
        tmp_path,
        Distributions.aaa_100_whl_27,
        Distributions.aaa_100_whl_33,
        Distributions.aaa_200_whl_33,
        Distributions.bbb_100_whl_27,
        Distributions.bbb_100_whl_33,
        Distributions.bad_dep_100_whl_33,
        Distributions.duplicate_deps_100_whl_33,
    )


@pytest.mark.parametrize(
    "bad_reqs",
    [
        ["It's go time"],
        ["aaa<2.0.0", "bbb==1.0.0", "mr_mandelbaum@ test======world_greatest_dad"],
        ["aaa<2.0.0", "mr_mandelbaum; oh_no='smug'", "bbb==1.0.0"],
        ["aaa<2.0.0", "bbb==1.0.0", "mandelbaum==2.0.0,"],
        ["aaa<2.0.0", "bbb==1.0.0", "tinsel,"],
        ["argparse; python_version == 2.6"],  # from Twine=1.1.0
    ],
)
def test_parse_requirements_bad_reqs(fake_depgraph_dataset: Depgraph, bad_reqs: list[str]) -> None:
    graph = PythonGraph(fake_depgraph_dataset, requires_python="3.3", platform="any")
    with pytest.raises(InvalidRequirementsError, match="Could not parse requirement"):
        graph.parse_requirements(requirements=bad_reqs)


@pytest.mark.parametrize(
    "bad_reqs",
    [
        ["boto3>=1.3.0", "prettytable>=0.7.0", "#objectpath>=0.5"],
        ["boto3>=1.3.0", "#objectpath>=0.5", "prettytable>=0.7.0"],
        ["boto3>=1.3.0", "     #objectpath>=0.5", "prettytable>=0.7.0"],
        ["boto3>=1.3.0", "prettytable>=0.7.0", "\t\t#objectpath>=0.5"],
    ],
)
def test_parse_requirements_with_comments(bad_reqs: list[str]) -> None:
    reqs = PythonGraph.parse_requirements(bad_reqs)
    assert len(reqs) == 2
    assert reqs[0].name == "boto3"  # type: ignore
    assert reqs[1].name == "prettytable"  # type: ignore


def test_dependencies_from_requirements(fake_depgraph_dataset: Depgraph) -> None:
    graph = PythonGraph(fake_depgraph_dataset, requires_python="3.3", platform="any")
    assert {
        AAA: {Distributions.aaa_100_whl_33},
        BBB: {Distributions.bbb_100_whl_33},
    } == graph.dependencies_from_requirements(requirements=graph.parse_requirements(["aaa<2.0.0", "bbb==1.0.0"]))


@pytest.mark.xfail(reason="https://github.com/toolchainlabs/toolchain/issues/3409", strict=True)
def test_dependencies_from_requirements_duplicate_deps(fake_depgraph_dataset: Depgraph) -> None:
    graph = PythonGraph(fake_depgraph_dataset, requires_python="3.3", platform="any")
    with pytest.raises(InvalidRequirementsError, match="Multiple constraints for project"):
        graph.dependencies_from_requirements(requirements=graph.parse_requirements(["aaa<=1.0.0", "aaa>=2.0.0"]))


@pytest.mark.xfail(reason="https://github.com/toolchainlabs/toolchain/issues/3409", strict=True)
def test_dependencies_from_requirements_duplicate_deps_root(fake_depgraph_dataset: Depgraph) -> None:
    # When we have duplicates in our requirements we should throw an error.
    graph = PythonGraph(fake_depgraph_dataset, requires_python="3.3", platform="any")
    with pytest.raises(InvalidRequirementsError, match="Multiple constraints for project"):
        graph.build_transitive_dependency_map(dependencies=graph.parse_requirements(["aaa<=1.0.0", "aaa>=2.0.0"]))


@pytest.mark.xfail(reason="https://github.com/toolchainlabs/toolchain/issues/3409", strict=True)
def test_dependencies_from_requirements_duplicate_deps_transitive(fake_depgraph_dataset: Depgraph) -> None:
    # When our transitive deps have duplicates in their requirements we should try to find a solution that avoids the
    # bad transitive dep and only fail if we can't find a solution.
    graph = PythonGraph(fake_depgraph_dataset, requires_python="3.3", platform="any")
    config = PythonConfig.for_dependencies(dependencies=["duplicatedeps"], graph=graph)
    resolver = Resolver(config)
    with pytest.raises(ResolutionError, match="Could not resolve conflict for"):
        resolver.run()
    assert "duplicatedeps" in graph._known_invalid_versions


@pytest.mark.parametrize(
    ("abi", "python_requirement", "expected_result"),
    [
        ({"", "none"}, "3.3", {Distributions.aaa_100_whl_33, Distributions.aaa_200_whl_33}),
        ({"", "none"}, "2.7.6", {Distributions.aaa_100_whl_27}),
        (
            {"", "none", "abi3"},
            "3.3",
            {Distributions.aaa_100_whl_33, Distributions.aaa_200_whl_33, Distributions.aaa_100_whl_33_abi3},
        ),
    ],
)
def test_fetch_all_versions_for(
    tmp_path: Path, abi: set[str], python_requirement: str, expected_result: set[PythonPackageDistribution]
) -> None:
    depgraph = create_fake_depgraph(
        tmp_path,
        Distributions.aaa_100_whl_27,
        Distributions.aaa_100_whl_27_osx,
        Distributions.aaa_100_whl_27_win,
        Distributions.aaa_100_whl_33,
        Distributions.aaa_100_whl_33_abi3,
        Distributions.aaa_200_whl_33,
        Distributions.core_schema_whl_2,
    )
    graph = PythonGraph(depgraph, valid_abis=abi, requires_python=python_requirement, platform="any")
    with pytest.raises(PackageNotFoundError, match="No distributions found for coreschema") as error_info:
        graph.fetch_all_versions_for("coreschema")
    assert error_info.value.to_dict() == {"msg": "No distributions found for coreschema", "package_name": "coreschema"}
    assert expected_result == graph.fetch_all_versions_for(AAA)


def test_fetch_dependencies_for_missing_dependency(tmp_path: Path) -> None:
    depgraph = create_fake_depgraph(tmp_path, Distributions.core_schema_whl_2)
    graph = PythonGraph(depgraph, valid_abis={"none"}, requires_python="2.7", platform="any")
    with pytest.raises(VersionNotFoundError, match="No matching distributions found for jinja") as error_info:
        graph.fetch_dependencies_for(Distributions.core_schema_whl_2)
    assert error_info.value.to_dict() == {
        "available_versions": [],
        "msg": "No matching distributions found for jinja",
        "package_name": "jinja",
    }


def test_fetch_dependencies_for_missing_dependency_version(tmp_path: Path) -> None:
    depgraph = create_fake_depgraph(tmp_path, Distributions.ccc_100_whl_33, Distributions.aaa_2012_whl_33)
    graph = PythonGraph(depgraph, valid_abis={""}, requires_python="3.3", platform="any")
    with pytest.raises(VersionNotFoundError, match="No matching distributions found for aaa==1.0") as error_info:
        graph.fetch_dependencies_for(Distributions.ccc_100_whl_33)
    assert error_info.value.to_dict() == {
        "available_versions": ["2.0.12"],
        "msg": "No matching distributions found for aaa==1.0",
        "package_name": "aaa",
    }


@pytest.mark.skip(reason="https://github.com/toolchainlabs/toolchain/issues/3409")
def test_missing_dependency(tmp_path: Path) -> None:
    depgraph = create_fake_depgraph(tmp_path, Distributions.core_schema_whl_3)
    graph = PythonGraph(depgraph, valid_abis={""}, requires_python="3.3", platform="any")
    config = PythonConfig.for_dependencies(dependencies=["coreschema"], graph=graph)
    resolver = Resolver(config)
    with pytest.raises(ResolutionError, match="Could not resolve conflict for"):
        resolver.run()


def test_fetch_dependencies_for(tmp_path: Path) -> None:
    depgraph = create_fake_depgraph(
        tmp_path,
        Distributions.aaa_100_whl_27,
        Distributions.aaa_100_whl_33,
        Distributions.aaa_200_whl_33,
        Distributions.bbb_100_whl_27,
        Distributions.bbb_100_whl_33,
        Distributions.bad_dep_100_whl_33,
        Distributions.ccc_100_whl_33,
    )
    graph = PythonGraph(depgraph, requires_python="3.3", platform="any")
    graph.build_transitive_dependency_map(dependencies=graph.parse_requirements(["bbb==1.0.0", "ccc==1.0.0"]))
    assert not graph.fetch_dependencies_for(Distributions.bbb_100_whl_33)
    assert {AAA: {Distributions.aaa_100_whl_33}} == graph.fetch_dependencies_for(Distributions.ccc_100_whl_33)
    assert not graph.fetch_dependencies_for(Interpreters.python_33)
    with pytest.raises(InvalidRequirementsError, match='Could not parse requirement "aaa==1.0,"') as error_info:
        graph.fetch_dependencies_for(Distributions.bad_dep_100_whl_33)
    assert str(error_info.value.parse_error) == "Parse error at \"','\": Expected string_end"


@pytest.mark.parametrize(
    ("dependencies", "requires_python", "platform", "result"),
    [
        (["bbb==1.0.0"], "2.7.6", "macosx_10_7_x86_64", [Distributions.aaa_100_whl_27, Distributions.bbb_100_whl_27]),
        (["bbb==1.0.0"], "3.3", "macosx_10_7_x86_64", [Distributions.bbb_100_whl_33]),
    ],
)
def test_resolve_with_interpreter_constraints(
    tmp_path: Path,
    dependencies: list[str],
    requires_python: str,
    platform: str,
    result: list[PythonPackageDistribution],
) -> None:
    depgraph = create_fake_depgraph(
        tmp_path,
        Distributions.aaa_100_whl_27,
        Distributions.aaa_100_whl_33,
        Distributions.aaa_200_whl_33,
        Distributions.bbb_100_whl_27,
        Distributions.bbb_100_whl_33,
    )
    graph = PythonGraph(depgraph, requires_python=requires_python, platform=platform)
    config = PythonConfig.for_dependencies(dependencies=dependencies, graph=graph)
    resolver = Resolver(config)
    resolver.run()
    assert result == resolver.result()


@pytest.mark.parametrize(
    ("dependencies", "abi", "requires_python", "platform", "result"),
    [
        (["aaa"], {"", "none"}, "3.3", "macosx_10_7_x86_64", [Distributions.aaa_100_whl_33]),
        (["aaa"], {"abi3"}, "3.3", "macosx_10_7_x86_64", [Distributions.aaa_200_whl_33_abi3]),
    ],
)
def test_resolve_with_abi_constraints(
    tmp_path: Path,
    dependencies: list[str],
    abi: set[str],
    requires_python: str,
    platform: str,
    result: list[PythonPackageDistribution],
) -> None:
    depgraph = create_fake_depgraph(
        tmp_path,
        Distributions.aaa_100_whl_27,
        Distributions.aaa_100_whl_33,
        Distributions.aaa_100_whl_33_abi3,
        Distributions.aaa_200_whl_33_abi3,
        Distributions.bbb_100_whl_27,
        Distributions.bbb_100_whl_33,
    )
    graph = PythonGraph(depgraph, valid_abis=abi, requires_python=requires_python, platform="any")
    config = PythonConfig.for_dependencies(dependencies=dependencies, graph=graph)
    resolver = Resolver(config)
    resolver.run()
    assert result == resolver.result()


@pytest.mark.parametrize(
    ("platform", "result"),
    [
        (
            "macosx_10_7_x86_64",
            {
                "macosx_10_6_fat32",
                "macosx_10_4_fat32",
                "macosx_10_3_universal",
                "macosx_10_7_fat64",
                "macosx_10_5_fat32",
                "macosx_10_1_universal",
                "macosx_10_6_universal",
                "macosx_10_7_x86_64",
                "macosx_10_5_universal",
                "macosx_10_4_intel",
                "macosx_10_0_fat32",
                "macosx_10_3_fat32",
                "macosx_10_6_intel",
                "macosx_10_2_universal",
                "macosx_10_2_fat32",
                "macosx_10_6_fat64",
                "macosx_10_4_universal",
                "macosx_10_5_intel",
                "macosx_10_1_fat32",
                "macosx_10_5_x86_64",
                "macosx_10_5_fat64",
                "macosx_10_7_universal",
                "macosx_10_7_intel",
                "macosx_10_7_fat32",
                "macosx_10_0_universal",
                "macosx_10_6_x86_64",
            },
        ),
        ("manylinux2010_x86_64", {"manylinux2010_x86_64", "manylinux1_x86_64"}),
        ("win64", {"win64"}),
    ],
)
def test_get_supported_platform_tags(platform: str, result: set[str]) -> None:
    assert result == get_supported_platform_tags(platform)


@pytest.mark.parametrize(
    ("req", "python_version", "result"),
    [
        ('importlib-resources~=1.0.2; python_version < "3.7"', "3.6", True),
        ('importlib-resources~=1.0.2; python_version < "3.7"', "3.8", False),
        # ('pytest-azurepipelines; extra == "azure-pipelines"', "3.8", True),
        ('importlib-metadata>=0.12; python_version < "3.8"', "3.8", False),
        ('importlib-metadata>=0.12; python_version < "3.8"', "3.5", True),
        ('defusedxml>=0.5.0rc1; python_version >= "3.0"', "2.7", False),
        ('defusedxml>=0.5.0rc1; python_version >= "3.0"', "3.8", True),
        ('defusedxml>=0.5.0rc1; python_version >= "3.0"', "3.0", True),
        ("urllib3!=1.25.0,!=1.25.1,<1.26,>=1.21.1", "3.8", True),
        ('enum34; python_version == "2.7"', "2.7", True),
        ('enum34; python_version == "2.7"', "3.6", False),
        ('typed-ast<1.5,>=1.4.0; implementation_name == "cpython" and python_version < "3.8"', "3.6", True),
        ('typed-ast<1.5,>=1.4.0; implementation_name == "cpython" and python_version < "3.8"', "3.8", False),
        ('funcsigs>=0.4; python_version == "2.7" or python_version == "2.6"', "2.7", True),
        ('funcsigs>=0.4; python_version == "2.7" or python_version == "2.6"', "3.6", False),
        ('cffi>=1.7; platform_python_implementation != "pypy"', "3.6", True),
        ('subprocess32>=3.2.7; python_version < "3"', "3.6", False),
        ('subprocess32>=3.2.7; python_version < "3"', "2.6", True),
        # ('subprocess32>=3.2.7; extra == "subprocess" and python_version < "3"', "3.6", False),
        # ('subprocess32>=3.2.7; extra == "subprocess" and python_version < "3"', "2.6", True),
        ('colorama; sys_platform == "win32"', "3.6", False),
        ('colorama; sys_platform == "any"', "3.6", True),
        ("cffi!=1.11.3,>=1.8", "3.6", True),
        ('win-inet-pton; (platform_system == "windows" and python_version < "3.3")', "2.7", False),
        ('win-inet-pton; (platform_system == "windows" and python_version < "3.3")', "3.4", False),
        # ('win-inet-pton; (platform_system == "windows" and python_version < "3.3") and extra == "socks"', "2.7", True),
        # ('win-inet-pton; (platform_system == "windows" and python_version < "3.3") and extra == "socks"', "3.4", False),
        ('funcsigs>=1; python_version < "3.3"', "3.6", False),
        # ('win-inet-pton; (sys_platform == "win32" and python_version == "2.7") and extra == "socks"', "2.7", True),
        ('win-inet-pton; (sys_platform == "win32" and python_version == "2.7")', "2.7", False),
    ],
)
def test_should_include(fake_depgraph_dataset: Depgraph, req: str, python_version: str, result: bool) -> None:
    # TODO: Re-enable all the reqs with "extra" markers once we figure out how to properly handle them.
    graph = PythonGraph(fake_depgraph_dataset, requires_python=python_version, platform="macosx_10_15_x86_64")
    assert should_include(graph=graph, req=pkg_resources.Requirement.parse(req)) is result
