# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import itertools
from collections.abc import Iterable

import networkx


def argmin(nodes: list[str]) -> int:
    """Return the index of the smallest element in the list."""
    min_val = None
    min_idx = -1
    for idx, node in enumerate(nodes):
        if min_val is None or node <= min_val:
            min_val = node
            min_idx = idx
    return min_idx


def canonical_rotation(cycle: list[str]) -> tuple[str, ...]:
    """Rotate the cycle representation so that it starts with the smallest node in node order.

    We designate this the canonical representation, for ease of testing etc.
    """
    min_idx = argmin(cycle)
    return tuple(cycle[min_idx : len(cycle)] + cycle[0:min_idx])


def find_cycles(edges: Iterable[tuple[str, str]], limit=100) -> tuple[tuple[str, ...], ...]:
    """Returns up to `limit` cycles in the given digraph.

    Uses Johnson's algorithm, which is O((#nodes+#edges)*#cycles)), and graphs can have an exponential number of simple
    cycles, so limiting is crucial.
    """
    graph = networkx.DiGraph(edges)
    return tuple(sorted(canonical_rotation(cycle) for cycle in itertools.islice(networkx.simple_cycles(graph), limit)))
