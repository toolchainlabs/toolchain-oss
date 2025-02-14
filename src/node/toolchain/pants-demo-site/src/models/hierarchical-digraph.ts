/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { rollUpNodes, rollUpEdges, EdgeMapping, sep } from './utils';

import NodeSet from '../models/NodeSet';
import { LeafNode, Node, RollupNode } from './Node';

class HierarchicalDigraph {
  labels: string[];
  allRolledUpNodes: NodeSet;
  allRolledUpEdges: EdgeMapping;

  constructor(leafNodes: Array<LeafNode>, edges: EdgeMapping) {
    this.labels = leafNodes.map(leafNode => {
      return leafNode.address;
    });
    this.allRolledUpNodes = rollUpNodes(leafNodes);
    this.allRolledUpEdges = rollUpEdges(edges);
  }

  findChildren(parent: string): Set<string> {
    const retValue = new Set<string>();
    for (const node of Array.from(this.allRolledUpNodes)) {
      const indexOfSecondSep = node.address
        .substring(parent.length + 1)
        .indexOf(sep);

      const retCondition =
        (parent === '' || node.address.startsWith(parent + sep)) &&
        indexOfSecondSep === -1;

      if (retCondition) {
        retValue.add(node.address);
      }
    }

    return retValue;
  }

  findNonTrivialChildren(parent: string): Set<string> {
    const ret: Set<string> = this.findChildren(parent);
    if (ret.size === 1) {
      const trivialChild: string = ret.values().next().value;
      const trivialChildsChildren: Set<string> =
        this.findNonTrivialChildren(trivialChild);
      if (trivialChildsChildren.size === 0) {
        return ret;
      }
      return trivialChildsChildren;
    }
    return ret;
  }

  findDescendants(parent: string): Set<string> {
    const retValue = new Set<string>();
    for (const node of Array.from(this.allRolledUpNodes)) {
      const retCondition =
        parent === '' || node.address.startsWith(parent + sep);
      if (retCondition) {
        retValue.add(node.address);
      }
    }

    return retValue;
  }

  getNodeEdges(nodeAddress: string) {
    const nodeEdges = this.allRolledUpEdges?.[nodeAddress];
    return nodeEdges
      ? Array.from(nodeEdges).filter(el => {
          return this.allRolledUpNodes.get(el)?.isLeaf();
        })
      : [];
  }

  leafTypeCounts(): Map<string, number> {
    const topLevelNodes = new Set<Node>();
    for (const topLevelNodeAddress of this.findChildren('')) {
      const topLevelNode = this.allRolledUpNodes.get(topLevelNodeAddress);
      if (topLevelNode !== undefined) {
        topLevelNodes.add(topLevelNode);
      }
    }
    const summedLeafTypes = new Map<string, number>();
    function add(leafType: string, addend: number) {
      summedLeafTypes.set(
        leafType,
        (summedLeafTypes.get(leafType) || 0) + addend
      );
    }
    for (const node of topLevelNodes) {
      if (node instanceof LeafNode && node.nodeType !== undefined) {
        add(node.nodeType, 1);
      } else if (node instanceof RollupNode) {
        for (const [leafType, count] of node.leafTypes) {
          add(leafType, count);
        }
      }
    }
    return summedLeafTypes;
  }
}

export default HierarchicalDigraph;
