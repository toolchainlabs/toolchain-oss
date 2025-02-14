# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from toolchain.util.hierarchicaldigraph.hierarchicaldigraph import (
    HierarchicalDigraph,
    VisibleGraph,
    roll_up_edges,
    roll_up_nodes,
    target_to_label,
)

_test_hierarchy = {
    "a": {
        "aa": {},
        "ab": {"aba": {}, "abb": {"abba": {}}},
        "ac": {},
    },
    "b": {
        "ba": {},
        "bb": {},
        "bc": {},
    },
    "c": {"ca": {"caa": {}, "cab": {}}},
}


_test_edges = {
    "a/aa": {"a/ab/aba", "b/bb", "b/bc"},
    "a/ab/abb/abba": {"c/ca/caa"},
    "b/ba": {"a/ac", "b/bb"},
    "b/bb": {"b/bc", "c/ca/caa", "c/ca/cab"},
}


def get_test_nodes() -> tuple[set[str], set[str]]:
    # Turn the human-readable hiearchy above into test data.
    all_nodes: set[str] = set()
    leaf_nodes: set[str] = set()

    def convert_test_hierarchy(prefix: str, data: dict):
        for k, v in data.items():
            path = "/".join([prefix, k]) if prefix else k
            if v == {}:
                leaf_nodes.add(path)
            else:
                convert_test_hierarchy(path, v)
            all_nodes.add(path)

    convert_test_hierarchy("", _test_hierarchy)
    return all_nodes, leaf_nodes


def test_find_non_trivial_children() -> None:
    nodes = {"foo/bar/baz", "foo/bar/qux", "foo/bar/qux/quux"}
    hd = HierarchicalDigraph(nodes, {})
    assert hd.find_non_trivial_children("") == {"foo/bar/baz", "foo/bar/qux"}
    assert hd.find_non_trivial_children("foo") == {"foo/bar/baz", "foo/bar/qux"}
    assert hd.find_non_trivial_children("foo/bar") == {"foo/bar/baz", "foo/bar/qux"}
    assert hd.find_non_trivial_children("foo/bar/qux") == {"foo/bar/qux/quux"}
    assert hd.find_non_trivial_children("foo/bar/qux/quux") == set()


def test_find_children() -> None:
    _, leaf_nodes = get_test_nodes()
    hd = HierarchicalDigraph(leaf_nodes, {})
    assert hd.find_children("") == {"a", "b", "c"}
    assert hd.find_children("a") == {"a/aa", "a/ab", "a/ac"}
    assert hd.find_children("a/aa") == set()
    assert hd.find_children("a/ab") == {"a/ab/aba", "a/ab/abb"}
    assert hd.find_children("a/ab/abb") == {"a/ab/abb/abba"}
    assert hd.find_children("c") == {"c/ca"}
    assert hd.find_children("c/ca") == {"c/ca/caa", "c/ca/cab"}


def test_find_descendants() -> None:
    all_nodes, leaf_nodes = get_test_nodes()
    hd = HierarchicalDigraph(leaf_nodes, {})
    assert hd.find_descendants("c") == {"c/ca", "c/ca/caa", "c/ca/cab"}
    assert hd.find_descendants("a/aa") == set()
    assert hd.find_descendants("") == all_nodes


def test_expand() -> None:
    _, leaf_nodes = get_test_nodes()
    hd = HierarchicalDigraph(leaf_nodes, _test_edges)
    vg = VisibleGraph.initial(hd)
    assert vg.visible_nodes == {"a", "b", "c"}
    assert vg.visible_edges == {
        "a": {"a", "b", "c"},
        "b": {"a", "b", "c"},
    }

    vga = vg.expand("a")
    assert vga.visible_nodes == {"a/aa", "a/ab", "a/ac", "b", "c"}
    assert vga.visible_edges == {
        "a/aa": {"a/ab", "b"},
        "a/ab": {"c"},
        "b": {"a/ac", "b", "c"},
    }

    vgab = vga.expand("b")
    assert vgab.visible_nodes == {"a/aa", "a/ab", "a/ac", "b/ba", "b/bb", "b/bc", "c"}
    assert vgab.visible_edges == {
        "a/aa": {"a/ab", "b/bb", "b/bc"},
        "a/ab": {"c"},
        "b/ba": {"a/ac", "b/bb"},
        "b/bb": {"b/bc", "c"},
    }

    assert vgab.collapse("b") == vga
    assert vga.collapse("a") == vg


def test_roll_up_nodes() -> None:
    all_nodes, leaf_nodes = get_test_nodes()
    assert roll_up_nodes(leaf_nodes) == all_nodes


def test_roll_up_edges() -> None:
    assert roll_up_edges(_test_edges) == {
        "a": {"a", "a/ab", "a/ab/aba", "b", "b/bb", "b/bc", "c", "c/ca", "c/ca/caa"},
        "a/aa": {"a", "a/ab", "a/ab/aba", "b", "b/bb", "b/bc"},
        "a/ab": {"c", "c/ca", "c/ca/caa"},
        "a/ab/abb": {"c", "c/ca", "c/ca/caa"},
        "a/ab/abb/abba": {"c", "c/ca", "c/ca/caa"},
        "b": {"a", "a/ac", "b", "b/bb", "b/bc", "c", "c/ca", "c/ca/caa", "c/ca/cab"},
        "b/ba": {"a", "a/ac", "b", "b/bb"},
        "b/bb": {"b", "b/bc", "c", "c/ca", "c/ca/caa", "c/ca/cab"},
    }


def test_target_to_label() -> None:
    assert (
        target_to_label(
            {
                "address": "a/aa/aaa",
            }
        )
        == "a/aa/aaa"
    )

    assert (
        target_to_label(
            {
                "address": "a/aa/aaa:foo",
            }
        )
        == "a/aa/aaa:foo"
    )

    assert target_to_label({"address": "3rdparty/python:fooreq", "requirements": ["fooreq==1.2.3"]}) == "fooreq==1.2.3"
