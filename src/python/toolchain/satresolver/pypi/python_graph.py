# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
import re
from collections import OrderedDict
from collections.abc import Sequence
from typing import Union

import pkg_resources
from packaging.markers import Marker

from toolchain.satresolver.graph import Graph, InvalidRequirementsError, PackageNotFoundError, VersionNotFoundError
from toolchain.satresolver.package import ROOT
from toolchain.satresolver.pypi.abi import ABI
from toolchain.satresolver.pypi.depgraph import Depgraph
from toolchain.satresolver.pypi.platforms import Platform
from toolchain.satresolver.pypi.python_distribution import PythonPackageDistribution
from toolchain.satresolver.pypi.python_interpreter import PythonInterpreter
from toolchain.satresolver.pypi.python_interpreter_versions import ALL_PYTHON_INTERPRETERS
from toolchain.satresolver.pypi.tags import ALL_PLATFORM_TAGS

PythonRequirements = list[pkg_resources.Requirement]
PythonDependencies = dict[str, frozenset[PythonPackageDistribution]]
PythonPackageVersion = Union[PythonInterpreter, Platform, ABI, PythonPackageDistribution]

_logger = logging.getLogger(__name__)
_osx_arch_pat = re.compile(r"(.+)_(\d+)_(\d+)_(.+)")
_DEFAULT_ABI_MAP = {
    "3.3": ("cp33m", "abi3"),
    "3.4": ("cp34m", "abi3"),
    "3.5": ("cp35m", "abi3"),
    "3.6": ("cp36m", "abi3"),
    "3.7": ("cp37m", "abi3"),
    "3.8": ("cp38", "abi3"),
}


def get_darwin_arches(major, minor, machine):
    """Return a list of supported arches (including group arches) for the given major, minor and machine architecture of
    an macOS machine."""
    # From https://github.com/pypa/pip/blob/master/src/pip/_internal/pep425tags.py
    arches = []

    def _supports_arch(arch):
        # Looking at the application support for macOS versions in the chart
        # provided by https://en.wikipedia.org/wiki/OS_X#Versions it appears
        # our timeline looks roughly like:
        #
        # 10.0 - Introduces ppc support.
        # 10.4 - Introduces ppc64, i386, and x86_64 support, however the ppc64
        #        and x86_64 support is CLI only, and cannot be used for GUI
        #        applications.
        # 10.5 - Extends ppc64 and x86_64 support to cover GUI applications.
        # 10.6 - Drops support for ppc64
        # 10.7 - Drops support for ppc
        #
        # Given that we do not know if we're installing a CLI or a GUI
        # application, we must be conservative and assume it might be a GUI
        # application and behave as if ppc64 and x86_64 support did not occur
        # until 10.5.
        #
        # Note: The above information is taken from the "Application support"
        #       column in the chart not the "Processor support" since I believe
        #       that we care about what instruction sets an application can use
        #       not which processors the OS supports.
        if arch == "ppc":
            return (major, minor) <= (10, 5)
        if arch == "ppc64":
            return (major, minor) == (10, 5)
        if arch == "i386":
            return (major, minor) >= (10, 4)
        if arch == "x86_64":
            return (major, minor) >= (10, 5)
        return arch in groups and any(_supports_arch(ga) for ga in groups[arch])

    groups = OrderedDict(
        [
            ("fat", ("i386", "ppc")),
            ("intel", ("x86_64", "i386")),
            ("fat64", ("x86_64", "ppc64")),
            ("fat32", ("x86_64", "i386", "ppc")),
        ]
    )

    if _supports_arch(machine):
        arches.append(machine)

    for garch in groups:
        if machine in groups[garch] and _supports_arch(garch):
            arches.append(garch)

    arches.append("universal")

    return arches


def get_supported_platform_tags(platform: str) -> set[str]:
    # Adaption from https://github.com/pypa/pip/blob/4f6bef6eb4e0eda92823c9b96412e01bf9fc60ca/src/pip/_internal/utils/compatibility_tags.py#L80
    arches = []
    arch_prefix, arch_sep, arch_suffix = platform.partition("_")
    if platform.startswith("macosx"):
        # support macosx-10.6-intel on macosx-10.9-x86_64
        match = _osx_arch_pat.match(platform)
        if match:
            name, major, minor, actual_arch = match.groups()
            tpl = f"{name}_{major}_%i_%s"
            for m in reversed(range(int(minor) + 1)):
                for a in get_darwin_arches(int(major), m, actual_arch):
                    arches.append(tpl % (m, a))
        else:
            # arch pattern didn't match (?!)
            arches.append(platform)
    elif arch_prefix == "manylinux2014":
        arches.append(platform)
        # manylinux1/manylinux2010 wheels run on most manylinux2014 systems
        # with the exception of wheels depending on ncurses. PEP 599 states
        # manylinux1/manylinux2010 wheels should be considered
        # manylinux2014 wheels:
        # https://www.python.org/dev/peps/pep-0599/#backwards-compatibility-with-manylinux2010-wheels
        if arch_suffix in {"i686", "x86_64"}:
            arches.extend((f"manylinux2010{arch_sep}{arch_suffix}", f"manylinux1{arch_sep}{arch_suffix}"))
    elif arch_prefix == "manylinux2010":
        # manylinux1 wheels run on most manylinux2010 systems with the
        # exception of wheels depending on ncurses. PEP 571 states
        # manylinux1 wheels should be considered manylinux2010 wheels:
        # https://www.python.org/dev/peps/pep-0571/#backwards-compatibility-with-manylinux1-wheels
        arches.extend((platform, f"manylinux1{arch_sep}{arch_suffix}"))
    else:
        arches.append(platform)

    return set(arches)


def get_abi_for_python_version(python_version: str) -> tuple[str, ...]:
    return _DEFAULT_ABI_MAP.get(python_version, ("abi3",))


class PythonGraph(Graph):
    # Note: This class will cache values fetched from the leveldb. This shouldn't prevent the resolve from working,
    # but please use a new instance of PythonGraph for each new resolve to make sure the cache size stays sane.

    # TODO Figure out a reasonable maxsize for the lru_caches.

    def __init__(
        self, depgraph: Depgraph, requires_python: str, platform: str, valid_abis: set[str] | None = None
    ) -> None:
        super().__init__()
        self._depgraph = depgraph
        self._abis: set[str] = valid_abis or set()
        self.valid_abis: set[str] = {"none", ""}.union(self._abis)
        self.requires_python = requires_python
        self._platform = platform
        self._platforms = get_supported_platform_tags(self._platform)

    def build_transitive_dependency_map(self, dependencies: PythonRequirements) -> None:
        """Builds the transitive dependency map from the root dependencies."""
        self._dependency_map[ROOT] = self.dependencies_for_root(dependencies)

    def fetch_all_versions_for(
        self, package_name: str
    ) -> set[PythonInterpreter] | set[Platform] | set[PythonPackageDistribution]:
        """Returns all versions of this package as a set of PythonPackageVersions.

        # TODO: There is no such thing as PythonPackageVersion.  This returns a set of either PythonInterpreter, # or
        Platform, or PythonPackageDistribution, and they don't share a common base type. # The parent class's version of
        this method claims to return Set[PackageVersion]. # Fix the type hierarchy, then fix this docstring, and add an
        appropriate type annotation.

        If the package does not exist, raises PackageNotFoundError
        """
        if package_name == PythonInterpreter.__name__:
            return {PythonInterpreter(interpreter="python", version=version) for version in ALL_PYTHON_INTERPRETERS}
        if package_name == Platform.__name__:
            return {Platform(platform=platform) for platform in ALL_PLATFORM_TAGS}
        all_versions = self.fetch_distributions_from_leveldb(package_name)
        if not all_versions:
            raise PackageNotFoundError(f"No distributions found for {package_name}", package_name)
        return all_versions

    def fetch_distributions_from_leveldb(self, package_name: str) -> set[PythonPackageDistribution]:
        all_versions = self._depgraph.get_distributions(package_name=package_name)

        def valid_python_requirement(requires_python):
            if not requires_python:
                return True
            try:
                return self.requires_python in pkg_resources.Requirement.parse(f"python{requires_python}")
            # TODO: Fix once https://github.com/pypa/setuptools/issues/2244 is resolved.
            except pkg_resources.extern.packaging.requirements.InvalidRequirement:
                return False

        compatible_versions = {
            dist
            for dist in all_versions
            if dist.abi in self.valid_abis
            and self.platform_match(dist.platform)
            and valid_python_requirement(dist.requires_python)
        }
        return compatible_versions

    def platform_match(self, platform: str) -> bool:
        if platform in {"any", ""}:
            return True
        return platform in self._platforms

    def fetch_dependencies_for(self, package_version: PythonPackageVersion) -> PythonDependencies:
        """Return a dictionary of the dependencies of package_version as package_name: set(PythonPackageVersions).

        If package version does not exist, raises PackageNotFoundError.
        """
        if isinstance(package_version, (PythonInterpreter, Platform, ABI)):
            return {}
        reqs = self.parse_requirements(package_version.requires)
        return self.dependencies_from_requirements(reqs)

    @classmethod
    def parse_requirements(cls, requirements: Sequence[str]) -> PythonRequirements:
        req_objects = []
        for requirement_string in requirements:
            if not requirement_string:
                continue
            requirement_string = requirement_string.strip().lower()
            if requirement_string.startswith("#"):
                continue
            req_objects.append(cls.parse_requirement(requirement_string))
        return req_objects

    @classmethod
    def parse_requirement(cls, requirement: str) -> pkg_resources.Requirement:
        try:
            return pkg_resources.Requirement.parse(requirement)
        # TODO: Fix once https://github.com/pypa/setuptools/issues/2244 is resolved.
        except pkg_resources.extern.packaging.requirements.InvalidRequirement as error:  # type: ignore
            raise InvalidRequirementsError(requirement, error)

    def dependencies_from_requirements(self, requirements: PythonRequirements) -> PythonDependencies:
        # Default value for "no requirements" in leveldb is ('',).
        dependencies: PythonDependencies = {}
        for req in requirements:
            if not should_include(graph=self, req=req):
                continue
            package_versions = self.all_versions(req.project_name)
            valid_distributions = frozenset(dist for dist in package_versions if dist.version in req)
            if not valid_distributions:
                raise VersionNotFoundError(
                    f"No matching distributions found for {req}",
                    project_name=req.project_name,
                    available_versions=[dist.version for dist in package_versions],
                )
            # https://github.com/toolchainlabs/toolchain/issues/5398 needs to be fixed before enabling this code.
            # if req.project_name in dependencies:
            #     raise PackageError(
            #         f"Multiple constraints for project {req.project_name}. Please specify each project only once.",
            #         req.project_name,
            #     )
            dependencies[req.project_name] = valid_distributions
        return dependencies

    def dependencies_for_root(self, requirements: PythonRequirements) -> PythonDependencies:
        return self.dependencies_from_requirements(requirements)

    def __str__(self) -> str:
        return f"python={self.requires_python} platform={self._platform} abis={self._abis}"


def should_include(graph: PythonGraph, req: pkg_resources.Requirement) -> bool:
    markers = req.marker
    if not markers:
        return True
    result = _check_markers_expression(graph, req, markers._markers)
    return result


def _check_markers_expression(graph, req, markers):
    result = None
    for marker in markers:
        if isinstance(marker, list):
            result = _check_markers_expression(graph, req, marker)
        elif marker == "or":
            if result is True:
                return True
            elif result is False:
                continue
            else:
                _logger.warning(f"Invalid markers expression: {req}. ignoring req.")
                return False
        elif marker == "and":
            if result is True:
                continue
            if result is False:
                return False
            _logger.warning(f"Invalid markers expression: {req}. ignoring req.")
            return False
        else:
            result = _check_marker(graph, req, marker)
    return result


def _check_marker(graph: PythonGraph, req: pkg_resources.Requirement, marker: Marker) -> bool:
    try:
        variable, op, value = marker  # type: ignore[misc]
    except ValueError:
        # HACK. Sometimes markers are wrapped in an extra list for no apparent reason. This should go away when
        # we can handle more complex markers.
        return False
    variable_str = str(variable)  # type: ignore[has-type]
    if variable_str == "extra":
        # TODO: Sometimes we *should* use extras. Figure out when.
        return False
    elif variable_str == "python_version":
        try:
            req = pkg_resources.Requirement.parse(f"python{op}{value}")  # type: ignore[has-type]
        except ValueError:
            return False
        if graph.requires_python in req:
            return True
        return False
    elif variable_str in {"sys_platform", "platform_system"}:
        return graph.platform_match(str(value))  # type: ignore[has-type]
    elif variable_str in {"platform_python_implementation", "implementation_name"}:
        # TODO: figure what is platform_python_implementation/implementation_name and how to handle it.
        return True
    else:
        _logger.warning(f"Unhandled marker: {req=} {variable=} {op=} {value=} {marker=}", exc_info=True)  # type: ignore[has-type]
    return True
