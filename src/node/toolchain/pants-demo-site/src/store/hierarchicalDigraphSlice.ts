/*
Copyright 2023 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { createSlice } from '@reduxjs/toolkit';
import { HD } from './types';
import HierarchicalDigraph from '../models/hierarchical-digraph';

const HierarchicalDigraphState: HD = {
  graph: undefined,
};

type Action = {
  payload: HierarchicalDigraph;
};

const hierarchicalDigraphSlice = createSlice({
  name: 'hierarchicalDigraph',
  initialState: HierarchicalDigraphState,
  reducers: {
    hierarchicalDigraphSet(state, action: Action) {
      state.graph = action.payload;
    },
  },
});

export const { hierarchicalDigraphSet } = hierarchicalDigraphSlice.actions;

export default hierarchicalDigraphSlice.reducer;
