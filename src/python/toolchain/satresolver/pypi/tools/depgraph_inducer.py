#!/usr/bin/env ./python
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from argparse import ArgumentParser
from collections.abc import Iterable

import pkg_resources
import plyvel

from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.lang.python.distributions.distribution_key import canonical_project_name
from toolchain.satresolver.pypi.depgraph import Depgraph

logger = logging.getLogger(__name__)


def induce_depgraph(input_depgraph_url: str, output_path: str, initial_req_strs: Iterable[str]):
    """Induces an existing depgraph down to the smaller graph spanned by the specified initial requirements.

    This is useful primarily for generating small depgraphs to test on.
    """
    input_depgraph = None
    output_db = None
    try:
        input_depgraph = Depgraph.from_url(input_depgraph_url)
        # First follow the deps of all the initial projects, transitively, to build up the list
        # of projects we want in the final db.
        projects_to_handle: set[str] = set()
        projects: set[str] = set()

        def handle_reqs(req_strs: Iterable[str]):
            try:
                for req in pkg_resources.parse_requirements(req_strs):
                    required_project = canonical_project_name(req.project_name)
                    if required_project not in projects:
                        projects_to_handle.add(required_project)
            # TODO: Fix once https://github.com/pypa/setuptools/issues/2244 is resolved.
            except pkg_resources.extern.packaging.requirements.InvalidRequirement as e:  # type: ignore
                logger.warning(f"Error parsing {req_strs}: {e}")

        handle_reqs(initial_req_strs)

        while projects_to_handle:
            project = canonical_project_name(projects_to_handle.pop())
            projects.add(project)
            for ppd in input_depgraph.get_distributions(project):
                handle_reqs(ppd.value.requires)
        logger.info(f"Found {len(projects)} projects to induce on.")

        # Now put all the dists for the projects we care about in the final db.
        output_db = plyvel.DB(output_path, create_if_missing=True)
        wb = output_db.write_batch()
        count = 0
        for project in sorted(projects):
            for key_bytes, value_bytes in input_depgraph.db.iterator(prefix=f"{project}\t".encode()):
                wb.put(key_bytes, value_bytes)
                count += 1
                if count % 100000 == 0:
                    wb.write()
                    logger.info(f"Wrote {count} dists.")
                    wb = output_db.write_batch()
        wb.write()
        logger.info(f"Wrote {count} dists.")
        output_db.compact_range()
        logger.info("Performed final compaction - Done.")

    finally:
        if input_depgraph:
            input_depgraph.close()
        if output_db:
            output_db.close()


class DepgraphInducer(ToolchainBinary):
    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        parser.add_argument("--input-depgraph-url", required=True, help="The depgraph to induce from.")
        parser.add_argument("--output-path", required=True, help="Write the resulting induced leveldb here.")
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--initial-requirements-file", help="The initial requirements file to induce over.")
        group.add_argument("--initial-requirements", action="append", help="The initial requirements to induce over.")

    def run(self) -> int:
        if self.cmdline_args.initial_requirements_file:
            with open(self.cmdline_args.initial_requirements_file) as fp:
                initial_req_strs = fp.readlines()
        else:
            initial_req_strs = self.cmdline_args.initial_requirements
        induce_depgraph(self.cmdline_args.input_depgraph_url, self.cmdline_args.output_path, initial_req_strs)
        return 0


if __name__ == "__main__":
    DepgraphInducer.start()
