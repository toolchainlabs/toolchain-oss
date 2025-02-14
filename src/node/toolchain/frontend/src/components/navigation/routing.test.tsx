/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';

import paths from 'utils/paths';
import Routing from './routing';
import render from '../../../tests/custom-render';
import queryClient from '../../../tests/queryClient';

const TESTING_HOST = 'http://localhost';

jest.mock('pages/builds/build-details', () => ({
  __esModule: true,
  default: () => <div>hello from the build details page</div>,
}));
jest.mock('utils/init-data', () => ({
  getHost: () => TESTING_HOST,
}));
const org = 'testorg';
const repo = 'testrepo';
const runId = 'run_id_testing';
const goalType = 'goal';
const runType = 'run';

const renderRoutes = (initRoute: string) =>
  render(
    <QueryClientProvider client={queryClient}>
      <Routing />
    </QueryClientProvider>,
    { wrapperProps: { pathname: initRoute } }
  );

describe('<Routing />', () => {
  afterEach(() => queryClient.clear());
  afterAll(() => jest.clearAllMocks());

  it('should render build details page on goal route', async () => {
    renderRoutes(paths.buildDetailsType(org, repo, runId, goalType));

    expect(screen.getByText('hello from the build details page')).toBeInTheDocument();
  });

  it('should render build details page on run route', async () => {
    renderRoutes(paths.buildDetailsType(org, repo, runId, runType));

    expect(screen.getByText('hello from the build details page')).toBeInTheDocument();
  });

  it('should render build details page on no type (just run_id)', async () => {
    renderRoutes(paths.buildDetails(org, repo, runId));

    expect(screen.getByText('hello from the build details page')).toBeInTheDocument();
  });

  it('should render 404 page on unknown url', async () => {
    renderRoutes('/unknown/');

    expect(screen.getByText(`404: Couldn't find this page`)).toBeInTheDocument();
  });
});
