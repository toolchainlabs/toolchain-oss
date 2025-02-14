/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

export class Node {
  readonly address: string;

  constructor(address: string) {
    this.address = address;
  }

  isLeaf() {
    return false;
  }
}

export class LeafNode extends Node {
  readonly nodeType: string | undefined;

  constructor(address: string, nodeType: string | undefined) {
    super(address);
    this.nodeType = nodeType;
  }

  isLeaf() {
    return true;
  }
}

export class RollupNode extends Node {
  // type -> number of leaves of that type under this node.
  readonly leafTypes: Map<string, number>;

  // Setting the leafTypes directly via the arg is only needed in tests.
  constructor(address: string, leafTypes?: Map<string, number>) {
    super(address);
    this.leafTypes = leafTypes || new Map<string, number>();
  }

  countLeaf(leafType: string) {
    const count = this.leafTypes.get(leafType) || 0;
    this.leafTypes.set(leafType, count + 1);
  }
}
