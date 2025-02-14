/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import HierarchicalDigraph from './hierarchical-digraph';
import { sep, rollUpNodes, rollUpEdges } from './utils';
import { LeafNode, RollupNode } from './Node';
import VisibleGraph from './visible-graph';
import NodeSet from './NodeSet';

type TestHierarchyType = {
  [key: string]: TestHierarchyType | string;
};

const testHierarchy = {
  a: {
    aa: 'target_type1',
    ab: { aba: 'target_type2', abb: { abba: 'target_type1' } },
    ac: 'target_type2',
  },
  b: {
    ba: 'target_type1',
    bb: 'target_type1',
    bc: 'target_type2',
  },
  c: { ca: { caa: 'target_type1', cab: 'target_type1' } },
};

const testEdges = {
  'a/aa': new Set(['a/ab/aba', 'b/bb', 'b/bc']),
  'a/ab/abb/abba': new Set(['c/ca/caa']),
  'b/ba': new Set(['a/ac', 'b/bb']),
  'b/bb': new Set(['b/bc', 'c/ca/caa', 'c/ca/cab']),
};

const expectedRollupData = {
  a: { target_type1: 2, target_type2: 2 },
  ab: { target_type1: 1, target_type2: 1 },
  abb: { target_type1: 1 },
  ac: { target_type2: 1 },
  b: { target_type1: 2, target_type2: 1 },
  c: { target_type1: 2 },
  ca: { target_type1: 2 },
};

const expectedTotalLeafTypeCounts = {
  target_type1: 6,
  target_type2: 3,
};

const getExpectedRollupNodes: () => Array<RollupNode> = () => {
  const ret: Array<RollupNode> = [];
  Object.entries(expectedRollupData).forEach(([k, v]) => {
    ret.push(new RollupNode(k, new Map(Object.entries(v))));
  });
  return ret;
};

const anotherTestLeafNodeAddressList = [
  'foo/bar/baz',
  'foo/bar/qux',
  'foo/bar/qux/quux',
];

const getTestLeafNodes: () => Array<LeafNode> = () => {
  const leafNodes: Array<LeafNode> = [];

  const convertTestHierarchy = (prefix: string, data: TestHierarchyType) => {
    Object.entries(data).forEach(([k, v]) => {
      const path = prefix ? [prefix, k].join(sep) : k;
      if (typeof v === 'string') {
        leafNodes.push(new LeafNode(path, v));
      } else {
        convertTestHierarchy(path, v);
      }
    });
  };
  convertTestHierarchy('', testHierarchy);
  return leafNodes;
};

describe('HierarchicalDigraph & VisibleGraph', () => {
  const leafNodes = getTestLeafNodes();
  const expectedRollupNodes = getExpectedRollupNodes();
  const expectedNodes = [...leafNodes, ...expectedRollupNodes];
  const expectedNodeSet = new NodeSet(expectedNodes);

  it('should roll up nodes correctly', () => {
    expect(rollUpNodes(leafNodes).isEqualTo(expectedNodeSet));
  });

  it('should roll up edges correctly', () => {
    const expectedResult = {
      a: new Set([
        'a',
        'a/ab',
        'a/ab/aba',
        'b',
        'b/bb',
        'b/bc',
        'c',
        'c/ca',
        'c/ca/caa',
      ]),
      'a/aa': new Set(['a', 'a/ab', 'a/ab/aba', 'b', 'b/bb', 'b/bc']),
      'a/ab': new Set(['c', 'c/ca', 'c/ca/caa']),
      'a/ab/abb': new Set(['c', 'c/ca', 'c/ca/caa']),
      'a/ab/abb/abba': new Set(['c', 'c/ca', 'c/ca/caa']),
      b: new Set([
        'a',
        'a/ac',
        'b',
        'b/bb',
        'b/bc',
        'c',
        'c/ca',
        'c/ca/caa',
        'c/ca/cab',
      ]),
      'b/ba': new Set(['a', 'a/ac', 'b', 'b/bb']),
      'b/bb': new Set(['b', 'b/bc', 'c', 'c/ca', 'c/ca/caa', 'c/ca/cab']),
    };

    const result = rollUpEdges(testEdges);
    expect(result).toEqual(expectedResult);
  });

  it('should find non trivial children', () => {
    const anotherTestNodesList = anotherTestLeafNodeAddressList.map(addr => {
      return new LeafNode(addr, 'unknown_type');
    });
    const hd = new HierarchicalDigraph(anotherTestNodesList, {});
    expect(hd.findNonTrivialChildren('')).toEqual(
      new Set(['foo/bar/baz', 'foo/bar/qux'])
    );
    expect(hd.findNonTrivialChildren('foo')).toEqual(
      new Set(['foo/bar/baz', 'foo/bar/qux'])
    );
    expect(hd.findNonTrivialChildren('foo/bar')).toEqual(
      new Set(['foo/bar/baz', 'foo/bar/qux'])
    );
    expect(hd.findNonTrivialChildren('foo/bar/qux')).toEqual(
      new Set(['foo/bar/qux/quux'])
    );
    expect(hd.findNonTrivialChildren('foo/bar/qux/quux')).toEqual(new Set());
  });

  it('should find children', () => {
    const hd = new HierarchicalDigraph(leafNodes, {});
    expect(hd.findChildren('')).toEqual(new Set(['a', 'b', 'c']));
    expect(hd.findChildren('a')).toEqual(new Set(['a/aa', 'a/ab', 'a/ac']));
    expect(hd.findChildren('a/aa')).toEqual(new Set());
    expect(hd.findChildren('a/ab')).toEqual(new Set(['a/ab/aba', 'a/ab/abb']));
    expect(hd.findChildren('a/ab/abb')).toEqual(new Set(['a/ab/abb/abba']));
    expect(hd.findChildren('c')).toEqual(new Set(['c/ca']));
    expect(hd.findChildren('c/ca')).toEqual(new Set(['c/ca/caa', 'c/ca/cab']));
  });

  it('should count total leaf types correctly', () => {
    const hd = new HierarchicalDigraph(leafNodes, {});
    const expected = new Map<string, number>(
      Object.entries(expectedTotalLeafTypeCounts)
    );
    const actual = hd.leafTypeCounts();
    expect(actual.size).toEqual(expected.size);
    for (const [leafType, count] of actual) {
      expect(count).toEqual(expected.get(leafType));
    }
  });

  it('should return target edges', () => {
    const leafNodes = getTestLeafNodes();
    const hd = new HierarchicalDigraph(leafNodes, testEdges);

    expect(hd.getNodeEdges('b/bb')).toEqual(['b/bc', 'c/ca/caa', 'c/ca/cab']);
    expect(hd.getNodeEdges('b/bc')).toEqual([]);
    expect(hd.getNodeEdges('fff')).toEqual([]);
  });

  it('should find visibility', () => {
    const hd = new HierarchicalDigraph(leafNodes, {});
    const vg = VisibleGraph.initial(hd);

    expect(vg.isVisible('a')).toBeTruthy();
    expect(vg.isVisible('b')).toBeTruthy();
    expect(vg.isVisible('c')).toBeTruthy();
    expect(vg.isVisible('a/aa')).toBeFalsy();
  });

  it('should find ancestor visibility', () => {
    const hd = new HierarchicalDigraph(leafNodes, {});
    const vg = VisibleGraph.initial(hd);

    expect(vg.hasVisibleDescendant('a')).toBeTruthy();
    expect(vg.hasVisibleDescendant('a/ab')).toBeFalsy();
    const vga = vg.expand('a');
    expect(vga.hasVisibleDescendant('a')).toBeTruthy();
    expect(vga.hasVisibleDescendant('a/ab')).toBeTruthy();
    expect(vga.hasVisibleDescendant('a/ab/abb')).toBeFalsy();
    const vgab = vga.expand('a/ab');
    expect(vgab.hasVisibleDescendant('a')).toBeTruthy();
    expect(vgab.hasVisibleDescendant('a/ab')).toBeTruthy();
    expect(vgab.hasVisibleDescendant('a/ab/abb')).toBeTruthy();
  });

  it('should expand and collapse nodes', () => {
    const hd = new HierarchicalDigraph(leafNodes, testEdges);
    const vg = VisibleGraph.initial(hd);

    expect(vg.visibleNodes).toEqual(new Set(['a', 'b', 'c']));
    expect(vg.visibleEdges).toEqual({
      a: new Set(['a', 'b', 'c']),
      b: new Set(['a', 'b', 'c']),
    });
    const vga = vg.expand('a');
    expect(vga.visibleNodes).toEqual(
      new Set(['a/aa', 'a/ab', 'a/ac', 'b', 'c'])
    );
    expect(vga.visibleEdges).toEqual({
      'a/aa': new Set(['a/ab', 'b']),
      'a/ab': new Set(['c']),
      b: new Set(['a/ac', 'b', 'c']),
    });

    const vgab = vga.expand('b');
    expect(vgab.visibleNodes).toEqual(
      new Set(['a/aa', 'a/ab', 'a/ac', 'b/ba', 'b/bb', 'b/bc', 'c'])
    );
    expect(vgab.visibleEdges).toEqual({
      'a/aa': new Set(['a/ab', 'b/bb', 'b/bc']),
      'a/ab': new Set(['c']),
      'b/ba': new Set(['a/ac', 'b/bb']),
      'b/bb': new Set(['b/bc', 'c']),
    });

    const vgabCollapsed = vgab.collapse('b');
    expect(vgabCollapsed.visibleNodes).toEqual(vga.visibleNodes);
    expect(vgabCollapsed.visibleEdges).toEqual(vga.visibleEdges);

    const vgaCollapsed = vga.collapse('a');
    expect(vgaCollapsed.visibleNodes).toEqual(vg.visibleNodes);
    expect(vgaCollapsed.visibleEdges).toEqual(vg.visibleEdges);
  });
});
