/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen, fireEvent } from '@testing-library/react';

import { useBuildsTableFiltersContext, QueryParams } from './builds-filters-store';
import render from '../../tests/custom-render';

const TestBuildsTableFilterStore = ({ slug, params }: { slug: string; params: QueryParams }) => {
  const { buildParams, setBuildParams } = useBuildsTableFiltersContext();

  return (
    <>
      <button
        data-testid="setBuildParamsButton"
        aria-label="setBuilds"
        onClick={() => setBuildParams(slug, params)}
        type="button"
      />
      {buildParams && Object.keys(buildParams).length && (
        <div data-testid="buildParams">{JSON.stringify(buildParams)}</div>
      )}
    </>
  );
};

const renderTestBuildsTableFilterStore = (slug: string = 'sameple repo', params?: QueryParams) =>
  render(<TestBuildsTableFilterStore slug={slug} params={params} />);

describe('useBuildsTableFilterStore', () => {
  it('should not render build params by default', () => {
    renderTestBuildsTableFilterStore();

    expect(screen.queryByTestId('buildParams')).not.toBeInTheDocument();
  });

  it('should display buildParams when changed', async () => {
    const newParamValues: QueryParams = {
      page_size: 1,
      page: 3,
      goals: ['param1', 'param2'],
      ci: false,
    };

    renderTestBuildsTableFilterStore('sameple repo', newParamValues);

    const button = screen.queryByTestId('setBuildParamsButton');

    fireEvent.click(button);

    expect(screen.getByTestId('buildParams')).toBeInTheDocument();
  });

  it('should store boolean in stringifyied version as 0 if false', async () => {
    const newParamValues: QueryParams = {
      ci: false,
    };

    renderTestBuildsTableFilterStore('sameple repo', newParamValues);

    const button = screen.queryByTestId('setBuildParamsButton');

    fireEvent.click(button);

    expect(screen.getByTestId('buildParams').innerHTML).toContain('0');
  });

  it('should store boolean in stringifyied version as 1 if true', async () => {
    const newParamValues: QueryParams = {
      ci: true,
    };

    renderTestBuildsTableFilterStore('sameple repo', newParamValues);

    const button = screen.queryByTestId('setBuildParamsButton');

    fireEvent.click(button);

    expect(screen.getByTestId('buildParams').innerHTML).toContain('1');
  });
});
