# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import csv
import logging
import os
from collections import defaultdict

from toolchain.base.toolchain_error import ToolchainError

logger = logging.getLogger(__name__)


class MavenArtifactSorter:
    """Sorts Maven artifacts topologically and returns the most depended-on artifacts.

    Note that, unfortunately, artifact-level deps are not a DAG, so we must detect and ignore cycles, and this isn't a
    true topological sort (as deps aren't a true partial relation).
    """

    class ContainsCycle(ToolchainError):
        def __init__(self):
            super().__init__()
            self._cycle = []

        def append(self, n):
            if len(self._cycle) < 2 or self._cycle[0] != self._cycle[-1]:  # We haven't noted the entire cycle yet.
                self._cycle.append(n)

        @property
        def cycle(self):
            return self._cycle

        def __str__(self):
            return "->".join(reversed(self._cycle))

    def __init__(self, coordinates_path, deps_path):
        self._coordinates_path = os.path.expanduser(coordinates_path)
        self._deps_path = os.path.expanduser(deps_path)
        self._id_to_coords = {}
        self._src_to_tgts = defaultdict(set)
        # Visit state.
        self._white = set()
        self._grey = set()
        self._black = set()
        self._sorted = []
        self._num_cycles = 0

    def load_coordinates(self):
        with open(self._coordinates_path, "rb") as fp:
            next(fp)  # Skip header.
            reader = csv.reader(fp)
            for row in reader:
                self._id_to_coords[row[0]] = row[1]
                self._white.add(row[0])
        logger.info(f"Loaded {len(self._id_to_coords)} coordinates")

    def load_deps(self):
        with open(self._deps_path, "rb") as fp:
            next(fp)  # Skip header.
            reader = csv.reader(fp)
            i = 0
            for row in reader:
                self._src_to_tgts[row[0]].add(row[1])
                i += 1
        logger.info(f"Loaded {i} dependencies")

    def sort(self):
        while self._white:
            try:
                self._visit(next(iter(self._white)))
            except self.ContainsCycle:
                # self._log_cycle(list(reversed(e.cycle)))
                self._num_cycles += 1
        if self._num_cycles:
            logger.error(f"Detected {self._num_cycles} cycles.")
        else:
            logger.info("Sorted.")

    def write_sorted(self, filepath):
        with open(filepath, "wb") as f:
            f.write("\n".join([self._id_to_coords[artifact_id] for artifact_id in self._sorted]))

    def head(self):
        for n in self._sorted[0:100]:
            logger.info(self._id_to_coords[n])

    def _visit(self, n):
        try:
            self._do_visit(n)
        except self.ContainsCycle as e:
            e.append(n)
            raise

    def _do_visit(self, n):
        if n in self._black:
            return
        self._white.discard(n)
        if n in self._grey:
            raise self.ContainsCycle()
        self._grey.add(n)
        for m in self._src_to_tgts.get(n, []):
            self._visit(m)
        self._grey.remove(n)
        self._black.add(n)
        self._sorted.append(n)

    def _log_cycle(self, cycle_ids):
        logger.info("Detected cycle:")
        cycle_coords = [self._id_to_coords[n] for n in cycle_ids]
        for n, c in zip(cycle_ids, cycle_coords):
            logger.info(f"{n}  {c}")
