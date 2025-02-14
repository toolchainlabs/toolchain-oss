# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from typing import Optional

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.lang.python.util import is_exact_requirement
from toolchain.satresolver.config import Config
from toolchain.satresolver.pypi.python_graph import PythonGraph, PythonRequirements

logger = logging.getLogger(__name__)


class PythonConfig(Config):
    """Configuration for resolving python dependencies."""

    @classmethod
    def for_dependencies(
        cls, dependencies: list[str], graph: PythonGraph, override_reqs=False, overrides: Optional[list[str]] = None
    ):
        requirements = graph.parse_requirements(dependencies)
        overrides_reqs = graph.parse_requirements(overrides) if overrides else None
        return cls.for_requirements(
            requirements=requirements, graph=graph, override_reqs=override_reqs, overrides=overrides_reqs
        )

    @classmethod
    def for_requirements(
        cls,
        requirements: PythonRequirements,
        graph: PythonGraph,
        override_reqs=False,
        overrides: Optional[PythonRequirements] = None,
    ):
        if override_reqs and overrides:
            raise ToolchainAssertion("override_reqs can't be True when overrides are specified.")
        if override_reqs:
            # Currently we treat any exact requirements in requirements.txt as overrides - that is,
            # the resolver must select these requirements.  We may want to have some other representation
            # of overrides, so that we can give an error if the repo has an exact requirement that isn't
            # compatible with some other requirement, and let the user decide if they want to override
            # or to loosen that exact requirement. But for now this lets us do overrides easily.
            overrides_reqs = graph.dependencies_from_requirements(
                [req for req in requirements if is_exact_requirement(req)]
            )
        else:
            overrides_reqs = graph.dependencies_from_requirements(overrides) if overrides else {}

        cfg = cls(
            dependencies=requirements,  # type: ignore
            overrides=overrides_reqs,  # type: ignore
            graph=graph,
            use_latest=None,
            locked=None,
            downgrades=None,
        )
        return cfg
