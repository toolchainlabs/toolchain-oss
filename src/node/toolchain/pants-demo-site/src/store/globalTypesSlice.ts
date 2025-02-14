/*
Copyright 2023 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { createSlice } from '@reduxjs/toolkit';
import { GlobalTypes, TypesMap } from './types';

const globalTypesState: GlobalTypes = { map: undefined };

type Action = {
  payload: TypesMap;
};

const globalTypesSlice = createSlice({
  name: 'globalType',
  initialState: globalTypesState,
  reducers: {
    globalTypesMapSet(state, action: Action) {
      state.map = action.payload;
    },
  },
});

export const { globalTypesMapSet } = globalTypesSlice.actions;

export default globalTypesSlice.reducer;
