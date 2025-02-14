/*
Copyright 2023 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { createSlice } from '@reduxjs/toolkit';
import { VG, NodeAdress } from './types';
import VisibleGraph from '../models/visible-graph';
import { sep } from '../models/utils';

const visibleGraphState: VG = {
  graph: undefined,
};

type Action<T> = {
  payload: T;
};

const visibleGraphSlice = createSlice({
  name: 'visibleGraph',
  initialState: visibleGraphState,
  reducers: {
    visibleGraphSet(state, action: Action<VisibleGraph>) {
      state.graph = action.payload;
    },
    visibleGraphExpanded(state, action: Action<NodeAdress>) {
      const expandedVg = state.graph?.expand(action.payload || '');
      state.graph = expandedVg;
    },
    visibleGraphExpandedDeep(state, action: Action<NodeAdress>) {
      const nodeAddress = action.payload;
      // eslint-disable-next-line no-case-declarations
      const nodePath = nodeAddress?.split(sep);
      // eslint-disable-next-line no-case-declarations
      let deepExpandedVg = state.graph;
      nodePath?.forEach((displayName, index) => {
        const currentLevelNode = [
          ...nodePath.slice(0, index),
          displayName,
        ].join(sep);
        const isNotExpanded = deepExpandedVg?.isVisible(currentLevelNode);
        if (isNotExpanded) {
          deepExpandedVg = deepExpandedVg?.expand(currentLevelNode);
        }
      });
      state.graph = deepExpandedVg;
    },
    visibleGraphCollapsed(state, action: Action<NodeAdress>) {
      const collapsedVg = state.graph?.collapse(action.payload || '');
      state.graph = collapsedVg;
    },
  },
});

export const {
  visibleGraphSet,
  visibleGraphExpanded,
  visibleGraphExpandedDeep,
  visibleGraphCollapsed,
} = visibleGraphSlice.actions;

export default visibleGraphSlice.reducer;
