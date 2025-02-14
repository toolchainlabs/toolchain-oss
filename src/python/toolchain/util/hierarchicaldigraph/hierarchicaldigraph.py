# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

# Code to demonstrate the concept of a "HierarchicalDigraph".
#
# A HierarchicalDigraph is a set of objects with two independent graph structures
# superimposed on them:
#
#   - A tree
#   - A directed graph
#
# In the tree, the original objects are the leaf nodes, and there are also intermediate
# non-leaf nodes to provide the hierarchy.
#
# In the directed graph, the original objects are the entire set of nodes, and there are directed
# edges between those nodes.
#
# This is useful for modeling source code: source files live on a filesystem, so they naturally
# participate in a hierarchical tree structure in which they are leaf nodes and the directories
# they live in are the intermediate nodes. However they also have import dependencies, which form a
# directed graph between the leaf nodes.
#
# When viewing the tree hierarchy, the intermediate nodes can be collapsed and expanded (like in a
# file browser widget). This allows a user to focus on just the parts of the hierarchy that are
# interesting to them. We'll call those the "visible nodes" in the tree.
#
# The original, fine-grained digraph induces a coarse-grained digraph on the visible nodes by
# "rolling up" the directed edges in the obvious way:
#
# - A leaf node x rolls up to a visible node X if X is the closest ancestor of x
#   among the visible nodes.
# - A fine-grained edge x -> y rolls up to a coarse-grained edge X -> Y
#   where x rolls up to X and y rolls up to Y.
#
# The code in this file demonstrates one way of computing and working with these visible node
# rollups. It does so by computing all possible rollups up front. Note that in this implementation
# we don't maintain parent or child pointers, and the hierarchy is expressed by string labels with
# a separator. Some operations (such as finding the children of a node) are therefore linear in the
# size of the graph, rather than in the size of the node, but we expect this to be fine in practice
# for the use cases we care about.


# We assume that the hierarchy is expressed by this separator in the label names.
sep = "/"


@dataclass
class HierarchicalDigraph:
    leaf_nodes: set[str]
    all_rolled_up_nodes: set[str]
    all_rolled_up_edges: dict[str, set[str]]

    def __init__(self, labels: set[str], edges: dict[str, set[str]]):
        self.leaf_nodes = labels
        self.all_rolled_up_nodes = roll_up_nodes(labels)
        self.all_rolled_up_edges = roll_up_edges(edges)

    def find_children(self, parent: str) -> set[str]:
        return {
            node
            for node in self.all_rolled_up_nodes
            if (parent == "" or node.startswith(parent + sep)) and node.find(sep, len(parent) + 1) == -1
        }

    def find_non_trivial_children(self, parent: str) -> set[str]:
        """Return the closest descendants of the parent, as long as there is more than one.

        This allows us to automatically expand "trivial" levels that have only a single entry.
        """
        ret: set[str] = self.find_children(parent)
        if len(ret) == 1:
            trivial_child = next(iter(ret))
            trivial_childs_children: set[str] = self.find_non_trivial_children(trivial_child)
            if len(trivial_childs_children) == 0:
                # If we cannot expand further, stop.
                return ret
            return trivial_childs_children
        return ret

    def find_descendants(self, parent: str) -> set[str]:
        return {node for node in self.all_rolled_up_nodes if (parent == "" or node.startswith(parent + sep))}


@dataclass
class VisibleGraph:
    hierarchical_digraph: HierarchicalDigraph
    visible_nodes: set[str]
    visible_edges: dict[str, set[str]]

    @classmethod
    def initial(cls, hierarchical_digraph: HierarchicalDigraph) -> VisibleGraph:
        return cls(hierarchical_digraph, hierarchical_digraph.find_non_trivial_children(""))

    def __init__(self, hierarchical_digraph: HierarchicalDigraph, visible_nodes: set[str]):
        self.hierarchical_digraph = hierarchical_digraph
        self.visible_nodes = visible_nodes
        self.visible_edges = {
            src: dsts.intersection(visible_nodes)
            for src, dsts in hierarchical_digraph.all_rolled_up_edges.items()
            if src in visible_nodes
        }

    def expand(self, node: str) -> VisibleGraph:
        new_visible_nodes = self.visible_nodes.difference({node}).union(
            self.hierarchical_digraph.find_non_trivial_children(node)
        )
        return self.__class__(self.hierarchical_digraph, new_visible_nodes)

    def collapse(self, node: str) -> VisibleGraph:
        new_visible_nodes = self.visible_nodes.difference(self.hierarchical_digraph.find_descendants(node)).union(
            {node}
        )
        return self.__class__(self.hierarchical_digraph, new_visible_nodes)


def roll_up_node(label: str) -> set[str]:
    """Return all rollups of the given node."""
    ret = set()
    rollup_label = ""
    for part in label.split(sep):
        rollup_label = sep.join([rollup_label, part]) if rollup_label else part
        ret.add(rollup_label)
    return ret


def roll_up_nodes(labels: set[str]) -> set[str]:
    """Return all rollups of the given nodes."""
    ret = set()
    for label in labels:
        ret.update(roll_up_node(label))
    return ret


def roll_up_edges(edges: dict[str, set[str]]) -> dict[str, set[str]]:
    """Return all possible directed edge rollups.

    src and dst are represented as string labels.

    Note that we include an edge from a node to itself if that's what the rollup indicates (e.g., a/b -> a/c rolls up to
    a -> a) but we probably want to ignore those in display.
    """
    all_edges = defaultdict(set)

    def add_all_rollups(src_label: str, dst_label: str):
        for src_rollup in roll_up_node(src_label):
            for dst_rollup in roll_up_node(dst_label):
                all_edges[src_rollup].add(dst_rollup)

    for src, dsts in edges.items():
        for dst in dsts:
            add_all_rollups(src, dst)

    return all_edges


def target_to_label(target: dict[str, Any]) -> str:
    """Convert a single target's data (from "./pants peek") into a useful label.

    "Useful" means meaningful for a demosite user who isn't familiar with Pants.

    NOTE: This is just to make working with this example code easier. In production code
      this would probably happen on the server, and the client will already receive sensible labels.
    """
    # First see if this is a requirement. If so, the requirement string ("PyYAML==6.0.0")
    # is much more useful than the synthetic target address ("3rdparty/python:PyYAML").
    requirements = target.get("requirements", [])
    if len(requirements) == 1:
        return requirements[0]
    return target["address"]


def edges_from_peek_data(peek_data: dict[str, Any]) -> HierarchicalDigraph:
    """Convert data as returned by `./pants peek ::` into a HierarchicalDigraph.

    The produced edges use "/" as a hierarchy separator.

    NOTE: This is just to make working with this example code easier. In production code
      this would probably happen on the server, and the client will already receive sensible labels.
    """
    address_to_label: dict[str, str] = {}
    target_list: list[dict[str, Any]] = peek_data["target_list"]

    for target in target_list:
        address_to_label[target["address"]] = target_to_label(target)
    labels = set(address_to_label.values())
    edges = {
        address_to_label[target["address"]]: {
            address_to_label[tgt_address] for tgt_address in target.get("dependencies", tuple())
        }
        for target in target_list
    }
    return HierarchicalDigraph(labels, edges)


if __name__ == "__main__":
    import json

    with open("/tmp/peekdata.json") as fp:
        hd = edges_from_peek_data(json.load(fp))
    vg = VisibleGraph.initial(hd)
