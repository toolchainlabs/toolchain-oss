/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { LeafNode, Node, RollupNode } from '../models/Node';
import NodeSet from '../models/NodeSet';

export const sep = '/';
export const doubleSlash = '//';
export const hashTag = '#';

export type EdgeMapping = {
  [key: string]: Set<string>;
};

//Remove duplicates
export const filterArrayOfNodes: (
  inputArray: Node[]
) => Array<Node> = inputArray => {
  return inputArray.filter(
    (item, index, arr) =>
      arr.findIndex(arrItem => arrItem.address === item.address) === index
  );
};

export const filterArrayOfStrings: (
  inputArray: string[]
) => string[] = inputArray => {
  return inputArray.filter((item, index, arr) => arr.indexOf(item) === index);
};

// Returns the ancestors of the label, in order from the label itself to its parent, etc.
export const getAncestors = (label: string): Array<string> => {
  const ret: Array<string> = [];
  let rollUpLabel = '';

  label.split(sep).forEach(part => {
    rollUpLabel = rollUpLabel ? [rollUpLabel, part].join(sep) : part;
    ret.push(rollUpLabel);
  });

  return ret.reverse();
};

export const rollUpNodes = (leafNodes: Iterable<LeafNode>) => {
  const ret: NodeSet = new NodeSet(leafNodes);

  for (const leafNode of leafNodes) {
    for (const ancestorAddress of getAncestors(leafNode.address)) {
      let rollupNode = ret.get(ancestorAddress);
      if (rollupNode === undefined) {
        rollupNode = new RollupNode(ancestorAddress);
        ret.add(rollupNode);
      }
      if (rollupNode instanceof RollupNode && leafNode.nodeType) {
        rollupNode.countLeaf(leafNode.nodeType);
      }
    }
  }

  return ret;
};

export const rollUpEdges = (edges: EdgeMapping) => {
  const allEdges: { [key: string]: Set<string> } = {};

  const addAllRollUps = (srcLabel: string, dstLabel: string) => {
    getAncestors(srcLabel).forEach(srcAncestorAddress => {
      getAncestors(dstLabel).forEach(dstAncestorAddress => {
        if (allEdges[srcAncestorAddress]) {
          allEdges[srcAncestorAddress].add(dstAncestorAddress);
        } else {
          allEdges[srcAncestorAddress] = new Set<string>([dstAncestorAddress]);
        }
      });
    });
  };

  Object.entries(edges).forEach(([src, dsts]) => {
    dsts.forEach(dst => {
      addAllRollUps(src, dst);
    });
  });

  return allEdges;
};

export const findParentAddress = (nodeAddress: string) => {
  if (!nodeAddress) {
    return '';
  }

  const splittedArr = nodeAddress.split(sep);
  if (splittedArr.length === 1) {
    return '';
  }

  return splittedArr.slice(0, -1).join(sep);
};

export const findSearchSegment = (
  originalString: string,
  searchParam: string,
  options?: {
    caseUnsensitive?: boolean;
  }
) => {
  const adjustedString = options?.caseUnsensitive
    ? originalString.toLocaleLowerCase()
    : originalString;
  const adjustedSearchParam = options?.caseUnsensitive
    ? searchParam.toLocaleLowerCase()
    : searchParam;
  const searchParamLength = searchParam.length || 0;
  const searchPosition = adjustedString.search(adjustedSearchParam);

  if (searchPosition < 0) {
    return ['', '', ''];
  }

  const firstPart = originalString.substring(0, searchPosition);
  const secondPart = originalString.substring(
    searchPosition,
    searchPosition + searchParamLength
  );
  const thirdPart = originalString.substring(
    searchPosition + searchParamLength
  );

  return [firstPart, secondPart, thirdPart];
};
