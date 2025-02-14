/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import {
  getEdgesFromInputData,
  convertEdges,
  convertNodes,
  initialAddressFormat,
} from './data-structure-utils';
import smallerExample from './mockData/small_example.json';
import largerExample from './mockData/large_example.json';
import HierarchicalDigraph from './models/hierarchical-digraph';
import VisibleGraph from './models/visible-graph';
import { LeafNode } from './models/Node';
import { sep, hashTag } from './models/utils';

const expectedEdges = {
  a: new Set(),
  'a/aa': new Set(['a/ab/aba', 'b/bb', 'b/bc']),
  'a/ab': new Set(),
  'a/ab/aba': new Set(),
  'a/ab/abb': new Set(),
  'a/ab/abb/abba': new Set(['c/ca/caa']),
  'a/ac': new Set(),
  b: new Set(),
  'b/ba': new Set(['a/ac', 'b/bb']),
  'b/bb': new Set(['b/bc', 'c/ca/caa', 'c/ca/cab']),
  'b/bc': new Set(),
  c: new Set(),
  'c/ca': new Set(),
  'c/ca/caa': new Set(),
  'c/ca/cab': new Set(),
};

const expectedNodes = [{ id: 'a' }, { id: 'b' }, { id: 'c' }];

const expectedLinks = [
  {
    source: {
      id: 'a',
    },
    target: {
      id: 'b',
    },
  },
  {
    source: {
      id: 'a',
    },
    target: {
      id: 'c',
    },
  },
  {
    source: {
      id: 'b',
    },
    target: {
      id: 'a',
    },
  },
  {
    source: {
      id: 'b',
    },
    target: {
      id: 'c',
    },
  },
];

describe('Data Structure Util Functions', () => {
  const edges = getEdgesFromInputData(smallerExample);
  const hd = new HierarchicalDigraph(
    smallerExample.map(el => new LeafNode(el.address, 'unknown_type')),
    edges
  );
  const vg = VisibleGraph.initial(hd);
  it('should get edges from input data', () => {
    expect(JSON.stringify(edges)).toBe(JSON.stringify(expectedEdges));
  });

  it('should convert nodes', () => {
    const nodes = convertNodes(vg.visibleNodes);
    expect(JSON.stringify(nodes)).toBe(JSON.stringify(expectedNodes));
  });

  it('should convert edges', () => {
    const links = convertEdges(vg.visibleEdges);
    expect(JSON.stringify(links)).toBe(JSON.stringify(expectedLinks));
  });

  it('should remove double slash symbol from the beginning of a string', () => {
    const testString = 'testString';
    expect(initialAddressFormat(`//${testString}`)).toBe(testString);
  });

  it('should return original string if it does not start with double slash & has no hasTags', () => {
    const testString = 'testString';
    expect(initialAddressFormat(testString)).toBe(testString);
  });

  it('should replace hash tag symbol with separator symbol', () => {
    const inputString = `part1${hashTag}part2`;
    const outputString = `part1${sep}part2`;
    expect(initialAddressFormat(inputString)).toBe(outputString);
  });
});

describe('Loading large data sets', () => {
  const edges = getEdgesFromInputData(largerExample);
  const hd = new HierarchicalDigraph(
    largerExample.map(el => new LeafNode(el.address, 'unknown_type')),
    edges
  );
  VisibleGraph.initial(hd);
});
