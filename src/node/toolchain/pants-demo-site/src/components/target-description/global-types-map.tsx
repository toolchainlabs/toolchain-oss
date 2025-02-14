/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { useSelector } from 'react-redux';
import { GlobalState } from '../../store/types';
import DisplayTypesMap from './display-types-map';

const GlobalTypesMap = () => {
  const globalTypes = useSelector(
    (state: GlobalState) => state.globalTypes.map
  );

  return <DisplayTypesMap types={globalTypes} label="In this repo" />;
};

export default GlobalTypesMap;
