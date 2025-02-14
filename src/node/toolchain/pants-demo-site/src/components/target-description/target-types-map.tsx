/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { useSelector } from 'react-redux';
import { RollupNode } from '../../models/Node';
import { GlobalState } from '../../store/types';
import DisplayTypesMap from './display-types-map';

type TargetTypesMapType = {
  fullName: string;
};

const TargetTypesMap = ({ fullName }: TargetTypesMapType) => {
  const hd = useSelector(
    (state: GlobalState) => state.hierarchicalDigraph.graph
  );

  const targetData = hd?.allRolledUpNodes.get(fullName);

  const isRollUp = targetData && !targetData.isLeaf();

  const types = isRollUp ? (targetData as RollupNode).leafTypes : undefined;

  return isRollUp ? (
    <DisplayTypesMap types={types} label="In this directory" />
  ) : null;
};

export default TargetTypesMap;
