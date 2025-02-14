# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from collections import defaultdict
from typing import Any

from toolchain.satresolver.package import PackageVersion


class ResultGraph:
    """Pretty prints the dependency graph.

    The transitive dependencies of any package will be shown only once, at the minimum depth the package is found.
    ex:

    given:
    - root depends on a:a:1.0.0
    - a:a:1.0.0 depends on b:b:1.0.0
    - b:b:1.0.0 depends on a:a:1.0.0
    - b:b:1.0.0 depends on c:c:1.0.0

    The rendered graph will show:

      - a:a:1.0.0
      | - b:b:1.0.0
        | - a:a:1.0.0  <--- note that the dependencies of a:a:1.0.0 are truncated here, as we've already seen them.
        | - c:c:1.0.0

    Nodes that have been seen previously will be rendered in white text.
    Nodes that are being seen for the first time are rendered in green.

    Note: Minimum depth is 1, not 0 - this simplifies matters elsewhere where __ROOT__ may be given depth 0,
    or where a max_depth of 0 (A __ROOT__ with no dependencies, also known as a resolve failure) may result in
    divide by 0 errors. (eg: rendering the d3 dependency graph)
    """

    def __init__(self, dependency_graph: dict[Any, list[Any]], direct_dependencies: dict[str, PackageVersion]):
        self.direct_dependencies = direct_dependencies
        self.dependency_graph = dependency_graph
        self.depth: defaultdict = defaultdict(lambda: float("inf"))
        self.seen: set[PackageVersion] = set()
        self.lines: list[str] = []
        self._has_run: bool = False

    def _find_minimum_depths(self, package_version: PackageVersion, depth: int = 1) -> None:
        # Avoid infinite loop on circular dependencies.
        if self.depth[package_version] <= depth:
            return
        self.depth[package_version] = min(self.depth[package_version], depth)
        for dep in self.dependency_graph[package_version]:
            self._find_minimum_depths(dep, depth + 1)

    def _already_seen(self, package_version: PackageVersion, depth: int) -> bool:
        return depth > self.depth[package_version] or package_version in self.seen

    def _make_lines(self, package_version: PackageVersion, depth: int = 1) -> list[str]:
        lines: list[str] = []
        seen = self._already_seen(package_version, depth)
        lines = [f"{'    ' * (depth - 1)}{'|' if depth > 1 else ''} - {package_version}"]
        if not seen:
            self.seen.add(package_version)
            for dep in self.dependency_graph[package_version]:
                lines.extend(self._make_lines(dep, depth + 1))
        return lines

    def run(self) -> list[str]:
        if self._has_run:
            return self.lines
        self._has_run = True
        for package in self.direct_dependencies.values():
            self._find_minimum_depths(package)
        for package in sorted(self.direct_dependencies.values()):
            self.lines.extend(self._make_lines(package))
        return self.lines

    def get_result_text(self) -> str:
        self.run()
        return "\n".join(self.lines)
