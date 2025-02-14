/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { useState, useCallback } from 'react';
import qs from 'query-string';
import constate from 'constate';
import { QueryParamConfig, DecodedValueMap, encodeQueryParams } from 'use-query-params';

import { queryParamConfig } from '../pages/builds/list';

export type QueryParams = DecodedValueMap<{ [key: string]: QueryParamConfig<any, any> }>;
export type RepoBuildsParams = { [key: string]: string };
export type RepoBuildsInitParams = { initParams?: { [key: string]: string } };

const useBuildsTableFilterStore = ({ initParams = null }: RepoBuildsInitParams) => {
  const [buildParams, setParams] = useState<RepoBuildsParams>(initParams || {});

  const setBuildParams = useCallback(
    (slug: string, params: QueryParams) => {
      const encodedParams = encodeQueryParams(queryParamConfig, params);
      const queryString = qs.stringify(encodedParams);

      setParams({ ...buildParams, [slug]: queryString.length > 0 ? `?${queryString}` : '' });
    },
    [buildParams]
  );

  return { buildParams, setBuildParams };
};

export const [BuildsTableFiltersProvider, useBuildsTableFiltersContext] = constate((props?: RepoBuildsInitParams) =>
  useBuildsTableFilterStore(props)
);
