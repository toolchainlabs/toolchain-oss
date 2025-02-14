/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import HierarchicalDigraph from './hierarchical-digraph';
import { EdgeMapping } from './utils';

class VisibleGraph {
  hierarchicalDigraph: HierarchicalDigraph;
  visibleNodes: Set<string>;
  visibleEdges: EdgeMapping;

  constructor(
    hierarchicalDigraph: HierarchicalDigraph,
    visibleNodeAddresses: Set<string>
  ) {
    this.hierarchicalDigraph = hierarchicalDigraph;
    this.visibleNodes = visibleNodeAddresses;
    const newVisibleEdges: EdgeMapping = {};
    Object.entries(hierarchicalDigraph.allRolledUpEdges).forEach(
      ([key, value]) => {
        let elementExists = false;
        visibleNodeAddresses.forEach(addr => {
          if (addr === key) {
            elementExists = true;
          }
        });
        if (elementExists) {
          newVisibleEdges[key] = new Set<string>();
          visibleNodeAddresses.forEach(addr => {
            if (value.has(addr)) {
              newVisibleEdges[key].add(addr);
            }
          });
        }
      }
    );
    this.visibleEdges = newVisibleEdges;
  }

  static initial(hierarchicalDigraph: HierarchicalDigraph) {
    return new VisibleGraph(
      hierarchicalDigraph,
      hierarchicalDigraph.findNonTrivialChildren('')
    );
  }

  isVisible(node_address: string) {
    return this.visibleNodes.has(node_address);
  }

  hasVisibleDescendant(node_address: string) {
    for (const key of Array.from(this.visibleNodes)) {
      if (key.indexOf(node_address) >= 0) {
        return true;
      }
    }
    return false;
  }

  expand(node_address: string) {
    const nonTrivialChildren =
      this.hierarchicalDigraph.findNonTrivialChildren(node_address);
    if (nonTrivialChildren.size === 0) {
      return this;
    }

    const retValue = new Set<string>();
    this.visibleNodes.forEach(addr => {
      if (addr !== node_address) {
        retValue.add(addr);
      }
    });
    nonTrivialChildren.forEach(el => retValue.add(el));
    return new VisibleGraph(this.hierarchicalDigraph, retValue);
  }

  collapse(node_address: string) {
    const retValue = new Set<string>();
    this.visibleNodes.forEach(addr => {
      const tempSet = this.hierarchicalDigraph.findDescendants(node_address);
      let isElIncluded = false;
      tempSet.forEach(tmpNodeAddr => {
        if (tmpNodeAddr === addr) {
          isElIncluded = true;
        }
      });

      if (!isElIncluded) {
        retValue.add(addr);
      }
    });

    retValue.add(node_address);
    return new VisibleGraph(this.hierarchicalDigraph, retValue);
  }
}

export default VisibleGraph;
