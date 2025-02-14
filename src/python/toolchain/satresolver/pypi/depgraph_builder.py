# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from collections.abc import Sequence

from toolchain.lang.python.distributions.distribution_data_builder import DistributionDataBuilder
from toolchain.lang.python.distributions.distribution_key import DistributionKey
from toolchain.satresolver.graph import InvalidRequirementsError
from toolchain.satresolver.pypi.python_distribution import ResolutionData
from toolchain.satresolver.pypi.python_graph import PythonGraph

logger = logging.getLogger(__name__)


class DepgraphBuilder(DistributionDataBuilder):
    """Utility code to build the serving data set representing the entire PyPI dist dep graph."""

    def _parse_requirements(self, key: DistributionKey, requirements: Sequence[str]) -> tuple[str, ...]:
        valid_requirements = []
        failed_reqs: list[tuple[str, str]] = []
        for requirement in requirements:
            requirement = requirement.strip()
            if not requirement or requirement.startswith("#"):
                failed_reqs.append((requirement, "comment/empty"))
                continue
            try:
                PythonGraph.parse_requirement(requirement)
            except InvalidRequirementsError as error:
                failed_reqs.append((requirement, repr(error)))
                continue
            valid_requirements.append(requirement)
        if failed_reqs:
            logger.warning(
                f"reqs_parse_failed for {key} reqs={len(requirements)} valid={len(valid_requirements)} invalid={len(failed_reqs)}: {failed_reqs}"
            )
        return tuple(valid_requirements)

    def process_row(
        self,
        key: DistributionKey,
        sha256_hexdigest: str,
        requires: list[str],
        requires_dist: list[str],
        modules: list[str],
    ) -> None:
        # If the requires are not parseable, we don't want to store them.
        # The resolver will retry to parse them  (PythonGraph.fetch_dependencies_for) every time this distribution is processed.
        # So we want to skip parsing it in the resolver if we know it will fail.
        # In case we want to "reset" this, because we have a more robust requirements parsing mechanism, we will need to
        # rebuild leveldb (there is a flag for it on the PeriodicallyUpdateLevelDb).
        requirements = self._parse_requirements(key, requires or requires_dist or [])
        value = ResolutionData.create(requirements=requirements, sha256_hexdigest=sha256_hexdigest)
        self.put(key.to_ordered_bytes(), value.to_bytes())
        self.item_handled()
