# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.util.graph.cycle import argmin, canonical_rotation, find_cycles


@pytest.mark.parametrize(
    ("nodes", "expected_argmin"),
    [
        ([], -1),
        (["a"], 0),
        (["a", "b"], 0),
        (["b", "a"], 1),
        (["a", "b", "c"], 0),
        (["a", "c", "b"], 0),
        (["b", "a", "c"], 1),
        (["b", "c", "a"], 2),
        (["c", "a", "b"], 1),
        (["c", "b", "a"], 2),
        (["b", "a", "c", "aa"], 1),
    ],
)
def test_argmin(nodes, expected_argmin):
    assert expected_argmin == argmin(nodes)


@pytest.mark.parametrize(
    ("cycle", "expected_rotation"),
    [
        ([], ()),
        (["a"], ("a",)),
        (["a", "b"], ("a", "b")),
        (["b", "a"], ("a", "b")),
        (["a", "b", "c"], ("a", "b", "c")),
        (["a", "c", "b"], ("a", "c", "b")),
        (["b", "a", "c"], ("a", "c", "b")),
        (["b", "c", "a"], ("a", "b", "c")),
        (["c", "a", "b"], ("a", "b", "c")),
        (["c", "b", "a"], ("a", "c", "b")),
        (["b", "a", "c", "aa"], ("a", "c", "aa", "b")),
    ],
)
def test_canonical_rotation(cycle, expected_rotation):
    assert expected_rotation == canonical_rotation(cycle)


@pytest.mark.parametrize(
    ("edge_pairs", "expected_cycles"),
    [
        ([], ()),
        ([("a", "b"), ("b", "a")], (("a", "b"),)),
        ([("a", "b"), ("b", "c"), ("c", "d")], ()),
        ([("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")], (("a", "b", "c", "d"),)),
        ([("a", "b"), ("b", "c"), ("c", "d"), ("d", "b")], (("b", "c", "d"),)),
        ([("a", "b"), ("b", "c"), ("c", "d"), ("d", "b"), ("d", "e")], (("b", "c", "d"),)),
        ([("a", "b"), ("b", "c"), ("c", "d"), ("d", "b"), ("e", "f"), ("f", "e")], (("b", "c", "d"), ("e", "f"))),
        ([("a", "b"), ("b", "c"), ("c", "d"), ("d", "b"), ("d", "e"), ("e", "c")], (("b", "c", "d"), ("c", "d", "e"))),
    ],
)
def test_find_cycles(edge_pairs, expected_cycles):
    cycles = find_cycles(edge_pairs)
    assert expected_cycles == cycles

    one_cycle = find_cycles(edge_pairs, limit=1)
    assert set(one_cycle).issubset(set(expected_cycles))
