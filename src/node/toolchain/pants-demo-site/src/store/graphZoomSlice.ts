/*
Copyright 2023 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { createSlice } from '@reduxjs/toolkit';
import { GraphZoom } from './types';

const graphZoomState: GraphZoom = { level: 1 };

type Action = {
  payload: number;
};

const graphZoomSlice = createSlice({
  name: 'graphZoom',
  initialState: graphZoomState,
  reducers: {
    graphZoomDifferenceSet(state, action: Action) {
      state.level = state.level + (action.payload || 0);
    },
    graphZoomLevelSet(state, action) {
      state.level = action.payload || 1;
    },
  },
});

export const { graphZoomDifferenceSet, graphZoomLevelSet } =
  graphZoomSlice.actions;

export default graphZoomSlice.reducer;
