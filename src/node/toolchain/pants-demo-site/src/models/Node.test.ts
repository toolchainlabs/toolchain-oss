/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { Node, LeafNode, RollupNode } from './Node';

describe('Node', () => {
  it('should not be leaf', () => {
    const myNode = new Node('');
    expect(myNode.isLeaf()).toBe(false);
  });
});

describe('LeafNode', () => {
  it('should be leaf', () => {
    const myNode = new LeafNode('', undefined);
    expect(myNode.isLeaf()).toBe(true);
  });
});

describe('RollupNode', () => {
  it('should not be leaf', () => {
    const myNode = new RollupNode('', undefined);
    expect(myNode.isLeaf()).toBe(false);
  });
});
