/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { EdgeMapping } from './models/utils';

import { InputDataType } from './api-calls/results-data';
import { sep, doubleSlash, hashTag } from './models/utils';
import { LinkType } from './dependency-graph';

export const initialAddressFormat = (address: string) => {
  const indexOfDobuleSlash = address.indexOf(doubleSlash);
  const indexOfHashTag = address.indexOf(hashTag);

  const hasLeadingDoubleSlash = indexOfDobuleSlash === 0;
  const noDoubleSlashAddress = hasLeadingDoubleSlash
    ? address.substring(2)
    : address;

  if (indexOfHashTag < 0) {
    return noDoubleSlashAddress;
  }

  return noDoubleSlashAddress.replace(hashTag, sep);
};

export const getEdgesFromInputData = (data: InputDataType) => {
  const retObj: EdgeMapping = {};
  data.forEach(el => {
    const formattedAddrss = initialAddressFormat(el.address);
    const elDeps = new Set<string>();
    el?.dependencies?.forEach(dep => {
      const formattedDep = initialAddressFormat(dep);
      elDeps.add(formattedDep);
    });
    retObj[formattedAddrss] = elDeps;
  });

  return retObj;
};

export const convertEdges = (edges: EdgeMapping) => {
  const retArr: Array<LinkType> = [];
  Object.entries(edges).forEach(([source, deps]) => {
    deps.forEach(dep => {
      retArr.push({
        source: {
          id: source,
        },
        target: {
          id: dep,
        },
      });
    });
  });

  const filteredArr = retArr.filter(link => link.source.id !== link.target.id);

  return filteredArr;
};

export const convertNodes = (nodes: Set<string>) => {
  const retArr: Array<{ id: string }> = [];
  nodes.forEach(addr =>
    retArr.push({
      id: addr,
    })
  );
  return retArr;
};
