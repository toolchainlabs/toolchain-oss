/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { Node } from '../models/Node';

export default class NodeSet implements Iterable<Node> {
  readonly addressToNode: Map<string, Node>;

  constructor(nodes: Iterable<Node> = []) {
    this.addressToNode = new Map<string, Node>();
    for (const node of Array.from(nodes)) {
      this.addressToNode.set(node.address, node);
    }
  }

  get size() {
    return this.addressToNode.size;
  }

  add(item: Node) {
    this.addressToNode.set(item.address, item);
  }

  get(address: string): Node | undefined {
    return this.addressToNode.get(address);
  }

  delete(item: Node) {
    this.addressToNode.delete(item.address);
  }

  has(item: Node) {
    return this.addressToNode.get(item.address) === item;
  }

  [Symbol.iterator](): Iterator<Node> {
    function* generate(nodes: Iterable<Node>) {
      for (const node of Array.from(nodes)) {
        yield node;
      }
    }
    return generate(this.addressToNode.values());
  }

  isEqualTo(otherSet: NodeSet) {
    if (this.addressToNode.size !== otherSet.addressToNode.size) {
      return false;
    }
    for (const key of Array.from(this.addressToNode.keys())) {
      if (!otherSet.addressToNode.has(key)) {
        return false;
      }
    }
    return true;
  }
}
