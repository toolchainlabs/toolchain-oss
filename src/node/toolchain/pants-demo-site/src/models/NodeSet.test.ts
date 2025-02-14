/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { LeafNode, Node } from './Node';
import NodeSet from './NodeSet';

describe('NodeSet', () => {
  let mySet = new NodeSet();
  const someNode1 = new LeafNode('1', 'unknown_type');
  const someNode2 = new LeafNode('2', 'unknown_type');
  const someNode3 = new LeafNode('3', 'unknown_type');

  beforeEach(() => {
    mySet = new NodeSet();
  });

  it('should set Set size automatically on add & delete', () => {
    expect(mySet.size).toBe(0);
    mySet.add(someNode1);
    expect(mySet.size).toBe(1);
    mySet.delete(someNode1);
    expect(mySet.size).toBe(0);
  });

  it('should set Set size automatically on initial add', () => {
    expect(mySet.size).toBe(0);
    mySet.add(someNode1);
    mySet.add(someNode2);
    expect(mySet.size).toBe(2);
  });

  it('should compare based on address field on initial add', () => {
    const someNode1Copy = new LeafNode('1', 'unknown_type');
    mySet.add(someNode1);
    mySet.add(someNode1Copy);
    expect(mySet.size).toBe(1);
  });

  it('should compare two sets', () => {
    const mySet2 = new NodeSet();
    expect(mySet.isEqualTo(mySet2)).toBeTruthy();

    mySet.add(someNode1);
    mySet.add(someNode2);
    mySet.add(someNode3);

    mySet2.add(someNode3);
    mySet2.add(someNode2);
    mySet2.add(someNode1);

    expect(mySet.isEqualTo(mySet2)).toBeTruthy();
    expect(mySet2.isEqualTo(mySet)).toBeTruthy();

    mySet.delete(someNode1);
    expect(mySet.isEqualTo(mySet2)).toBeFalsy();
  });

  it('should be iterable', () => {
    const mySet = new NodeSet();
    mySet.add(someNode1);
    mySet.add(someNode2);
    mySet.add(someNode3);

    const iterated: Set<Node> = new Set<Node>();
    for (const node of mySet) {
      iterated.add(node);
    }
    expect(iterated).toEqual(new Set<Node>([someNode1, someNode2, someNode3]));
  });
});
