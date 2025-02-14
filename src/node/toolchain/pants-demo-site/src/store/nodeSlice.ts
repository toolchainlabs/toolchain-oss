/*
Copyright 2023 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { createSlice } from '@reduxjs/toolkit';
import { Node, NodeAdress } from './types';

const nodeState: Node = {
  focusedNode: undefined,
  hoveredNode: undefined,
  selectedNode: undefined,
};

type Action = {
  payload: NodeAdress;
};

const nodeSlice = createSlice({
  name: 'node',
  initialState: nodeState,
  reducers: {
    nodeSelected(state, action: Action) {
      state.selectedNode = action.payload;
    },
    nodeFocused(state, action) {
      state.focusedNode = action.payload;
    },
    nodeHovered(state, action) {
      state.hoveredNode = action.payload;
    },
  },
});

export const { nodeSelected, nodeFocused, nodeHovered } = nodeSlice.actions;

export default nodeSlice.reducer;
