/*
Copyright 2019 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { Route, Routes } from 'react-router-dom';
import { fireEvent, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import nock from 'nock';
import MockDate from 'mockdate';
import { QueryClientProvider } from '@tanstack/react-query';
import qs from 'query-string';

import NotFound from 'pages/not-found';
import { BuildsListResponse } from 'common/interfaces/builds';
import paths from 'utils/paths';
import ListBuildsPage from './list';
import branches from '../../../tests/__fixtures__/branches';
import buildsListMock from '../../../tests/__fixtures__/builds-list';
import goals from '../../../tests/__fixtures__/goals';
import users from '../../../tests/__fixtures__/users';
import repos from '../../../tests/__fixtures__/repos';
import orgs from '../../../tests/__fixtures__/orgs';
import render from '../../../tests/custom-render';
import queryClient from '../../../tests/queryClient';

const TESTING_HOST = 'http://localhost';
const org = 'toolchaindev';
const repo = 'toolchain';
const sampleUser = {
  api_id: 'efdo01831jd1',
  avatar_url: 'https://avatars1.githubusercontent.com/u/35751794?s=200&v=4',
  full_name: 'Random User',
  email: 'email',
  username: 'random',
};
const prNumbers = ['200', '400', '321', '123'];

const renderListBuilds = (
  queryString: string = '',
  user: typeof sampleUser = null,
  customOrg: string = org,
  customRepo: string = repo
) =>
  render(
    <QueryClientProvider client={queryClient}>
      <Routes>
        <Route path="/organizations/:orgSlug/repos/:repoSlug/builds/" element={<ListBuildsPage />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </QueryClientProvider>,
    {
      wrapperProps: { pathname: paths.builds(customOrg, customRepo), search: queryString },
      providerProps: { user: { initUser: user } },
    }
  );

const openWindowMock = jest.fn();

jest.mock('utils/datetime-formats', () => ({
  ...Object.assign(jest.requireActual('utils/datetime-formats')),
  dateTimeToLocal: (value: any) => value,
}));
jest.mock('utils/init-data', () => ({
  getHost: () => TESTING_HOST,
}));
jest.mock('utils/hooks/access-token');
jest.spyOn(window, 'open').mockImplementation(openWindowMock);

describe('ListBuilds', () => {
  beforeEach(() => {
    nock.cleanAll();
    queryClient.clear();
    MockDate.set(new Date('2019-05-14T11:01:58.135Z'));
  });

  afterEach(() => {
    MockDate.reset();
  });

  afterAll(() => {
    nock.cleanAll();
    nock.restore();
    jest.clearAllMocks();
    queryClient.clear();
  });

  it('should render table', async () => {
    const response: BuildsListResponse = { results: buildsListMock, total_pages: 3, max_pages: 3, page: 1 };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    const { asFragment } = renderListBuilds();

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should show loader', async () => {
    const response: BuildsListResponse = { results: buildsListMock, total_pages: 3, max_pages: 3, page: 1 };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    const { asFragment } = renderListBuilds();

    expect(asFragment()).toMatchSnapshot();

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    scope.done();
  });

  it('should show error', async () => {
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(403, {
        details: 'Error during API request',
      })
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    const { asFragment } = renderListBuilds();

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should close error message on click', async () => {
    const user = userEvent.setup();
    const response = {
      details: 'Error during API request',
    };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(403, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    const errorModal = await screen.findByRole('alert');

    expect(errorModal).toBeInTheDocument();

    user.click(document.body);

    await waitFor(() => expect(screen.queryByRole('alert')).toBeNull());

    scope.done();
  });

  it('should render with sorted outcome descending', async () => {
    const queryObj = { sort: '-outcome', user: users[0].username };
    const queryString = qs.stringify(queryObj);
    const response: BuildsListResponse = { results: buildsListMock, total_pages: 3, max_pages: 3, page: 1 };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(100)
      .query({ ...queryObj, page: 1 })
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ ...queryObj, page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    const { asFragment } = renderListBuilds(queryString);

    await waitFor(() => expect(screen.queryByText('User loading...')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should render with sorted outcome ascending', async () => {
    const queryObj = { sort: 'outcome', user: users[0].username };
    const queryString = qs.stringify(queryObj);
    const response: BuildsListResponse = { results: buildsListMock, total_pages: 3, max_pages: 3, page: 1 };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(100)
      .query({ ...queryObj, page: 1 })
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ ...queryObj, page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    const { asFragment } = renderListBuilds(queryString);

    await waitFor(() => expect(screen.queryByText('User loading...')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should render with query params as filters', async () => {
    const queryObj = {
      sort: 'timestamp',
      user: users[0].username,
      earliest: '2020-10-22%2022%3A08%3A36',
      branch: 'branch-1',
      goals: 'goal-1',
      outcome: 'SUCCESS',
    };
    const queryString = qs.stringify(queryObj);
    const response: BuildsListResponse = { results: buildsListMock, total_pages: 3, max_pages: 3, page: 1 };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(100)
      .query({ ...queryObj, page: 1 })
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ ...queryObj, page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    const { asFragment } = renderListBuilds(queryString);

    await waitFor(() => expect(screen.queryByText('User loading...')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should render filters on filter button click', async () => {
    const response: BuildsListResponse = { results: buildsListMock, total_pages: 3, max_pages: 3, page: 1 };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.queryByText('Filters')).toBeNull();

    fireEvent.click(screen.getByLabelText('show filters'));

    expect(screen.getByText('Filters')).toBeInTheDocument();

    scope.done();
  });

  it('should render filtered by CI', async () => {
    const queryObj = { ci: '1', user: users[0].username };
    const queryString = qs.stringify(queryObj);
    const response: BuildsListResponse = { results: buildsListMock, total_pages: 3, max_pages: 3, page: 1 };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(100)
      .query({ ci: true, user: users[0].username, page: 1 })
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1, ci: true, user: users[0].username })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    const { asFragment } = renderListBuilds(queryString);

    await waitFor(() => expect(screen.queryByText('User loading...')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should render no builds message', async () => {
    const response: BuildsListResponse = { results: [], total_pages: 3, max_pages: 3, page: 1 };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.getByText(/there are no builds in this repository/i)).toBeInTheDocument();

    scope.done();
  });

  it('should render no personal builds message', async () => {
    const response: BuildsListResponse = { results: [], total_pages: 3, max_pages: 3, page: 1 };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(100)
      .query({ user: 'me', page: 1 })
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1, user: 'me' })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    fireEvent.click(screen.queryByTitle(/my builds/i));

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.getByText(/you haven’t run any builds yet/i)).toBeInTheDocument();

    scope.done();
  });

  it('should render no personal ci builds message', async () => {
    const response: BuildsListResponse = { results: [], total_pages: 3, max_pages: 3, page: 1 };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(100)
      .query({ ci: true, page: 1, user: 'me' })
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1, user: 'me', ci: true })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    fireEvent.click(screen.queryByTitle(/my ci builds/i));

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.getByText(/you have no ci builds in this repository/i)).toBeInTheDocument();

    scope.done();
  });

  it('should render no personal desktop builds message', async () => {
    const response: BuildsListResponse = { results: [], total_pages: 3, max_pages: 3, page: 1 };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(100)
      .query({ page: 1, user: 'me', ci: false })
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1, user: 'me', ci: false })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    fireEvent.click(screen.queryByTitle(/my desktop builds/i));

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.getByText(/you have no desktop builds in this repository/i)).toBeInTheDocument();

    scope.done();
  });

  it('should render no ci builds message', async () => {
    const response: BuildsListResponse = { results: [], total_pages: 3, max_pages: 3, page: 1 };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(100)
      .query({ page: 1, ci: true })
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1, ci: true })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    fireEvent.click(screen.queryByTitle(/all ci builds/i));

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.getByText(/there are no ci builds in this repository/i)).toBeInTheDocument();

    scope.done();
  });

  it('should render two anchors in build context for ci builds', async () => {
    const queryObj = { ci: 1, user: users[0].username };
    const queryString = qs.stringify(queryObj);
    const response: BuildsListResponse = {
      results: buildsListMock.filter(build => build.is_ci),
      total_pages: 3,
      max_pages: 3,
      page: 1,
    };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(100)
      .query({ ci: true, user: users[0].username, page: 1 })
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ ci: true, page: 1, user: users[0].username })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds(queryString);

    const table = await screen.findByRole('grid');

    await waitFor(() => expect(screen.queryByText('User loading...')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    const tableBodyRows = table.querySelectorAll('tbody tr');

    tableBodyRows.forEach(row => {
      row.querySelectorAll("[data-colindex='8']").forEach(cell => {
        expect(cell.querySelectorAll('a')).toHaveLength(2);
      });
    });

    scope.done();
  });

  it('should render correct anchors href in build context for ci builds', async () => {
    const queryObj = { ci: '1', user: users[0].username };
    const queryString = qs.stringify(queryObj);
    const response: BuildsListResponse = {
      results: buildsListMock.filter(build => build.is_ci),
      total_pages: 3,
      max_pages: 3,
      page: 1,
    };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(100)
      .query({ ci: true, user: users[0].username, page: 1 })
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ ci: true, page: 1, user: users[0].username })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds(queryString);

    const table = await screen.findByRole('grid');

    await waitFor(() => expect(screen.queryByText('User loading...')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    const tableBodyRows = table.querySelectorAll('tbody tr');

    tableBodyRows.forEach(row => {
      row.querySelectorAll("[data-colindex='8']").forEach(cell => {
        expect(cell.querySelectorAll('a')[0]).toHaveAttribute('href', 'https://github.com/');
        expect(cell.querySelectorAll('a')[1]).toHaveAttribute('href', 'https://travis-ci.com/');
      });
    });

    scope.done();
  });

  it('should not render anchors in build context for desktop builds', async () => {
    const queryObj = { ci: '0', user: users[0].username };
    const queryString = qs.stringify(queryObj);
    const response: BuildsListResponse = {
      results: buildsListMock.filter(build => !build.is_ci),
      total_pages: 3,
      max_pages: 3,
      page: 1,
    };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(100)
      .query({ ci: false, user: users[0].username, page: 1 })
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ ci: false, page: 1, user: users[0].username })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds(queryString);

    const table = await screen.findByRole('grid');

    await waitFor(() => expect(screen.queryByText('User loading...')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    const tableBodyRows = table.querySelectorAll('tbody tr');

    tableBodyRows.forEach(row => {
      row.querySelectorAll("[data-colindex='8']").forEach(cell => {
        expect(cell).not.toContain('a');
      });
    });

    scope.done();
  });

  it('should not render title of toolbar if three or less goals present', async () => {
    const response: BuildsListResponse = {
      results: buildsListMock.filter(build => build.goals.length && build.goals.length <= 3),
      total_pages: 3,
      max_pages: 3,
      page: 1,
    };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    const table = await screen.findByRole('grid');

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    const tableBodyRows = table.querySelectorAll('tbody tr');

    tableBodyRows.forEach(row => {
      row.querySelectorAll("[data-colindex='6']").forEach(async cell => {
        expect(cell.querySelectorAll("[title='*']")).toHaveLength(0);
      });
    });

    scope.done();
  });

  it('should render title toolbar if more than 3 goals present', async () => {
    const response: BuildsListResponse = {
      results: buildsListMock.filter(build => build.goals.length && build.goals.length > 3),
      total_pages: 3,
      max_pages: 3,
      page: 1,
    };

    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    const table = await screen.findByRole('grid');

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    const tableBodyRows = table.querySelectorAll('tbody tr');

    tableBodyRows.forEach(row => {
      row.querySelectorAll("[data-colindex='6']").forEach(async cell => {
        expect(cell.querySelectorAll("[title='goal-1, goal-2, goal-3']")).toHaveLength(1);
      });
    });

    scope.done();
  });

  it('should render filter tabs', async () => {
    const response: BuildsListResponse = {
      results: buildsListMock,
      total_pages: 3,
      max_pages: 3,
      page: 1,
    };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.getByRole('tablist')).toBeInTheDocument();
    expect(screen.getByTitle('My Builds')).toBeInTheDocument();
    expect(screen.getByTitle('My CI Builds')).toBeInTheDocument();
    expect(screen.getByTitle('My Desktop Builds')).toBeInTheDocument();
    expect(screen.getByTitle('All CI Builds')).toBeInTheDocument();
    expect(screen.getByTitle('All Builds')).toBeInTheDocument();

    scope.done();
  });

  it('should change filter tabs on click', async () => {
    const response: BuildsListResponse = {
      results: [buildsListMock[0]],
      total_pages: 3,
      max_pages: 3,
      page: 1,
    };
    const ciResponse: BuildsListResponse = {
      results: buildsListMock.filter(build => build.is_ci),
      total_pages: 3,
      max_pages: 3,
      page: 1,
    };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(200)
      .query({ ci: true, page: 1, user: 'me' })
      .reply(200, ciResponse)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ ci: true, page: 1, user: 'me' })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    fireEvent.click(screen.queryByTitle('My CI Builds'));

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.queryByTitle('My CI Builds')).toHaveAttribute('aria-selected', 'true');

    scope.done();
  });

  it('should render all ci builds tab as selected since query contains the filter', async () => {
    const queryObj = { ci: '1' };
    const queryString = qs.stringify(queryObj);
    const response: BuildsListResponse = {
      results: buildsListMock.filter(build => build.is_ci),
      total_pages: 3,
      max_pages: 3,
      page: 1,
    };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1, ci: true })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1, ci: true })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds(queryString);

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.queryByTitle('All CI Builds')).toHaveAttribute('aria-selected', 'true');

    scope.done();
  });

  it('should show error if response is undefined', async () => {
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(500, undefined)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    await screen.findByRole('alert');

    expect(screen.getByRole('alert')).toBeInTheDocument();

    scope.done();
  });

  it('should render view on github button and link', async () => {
    const response: BuildsListResponse = {
      results: buildsListMock,
      total_pages: 3,
      max_pages: 3,
      page: 1,
    };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    const button = screen.queryByText('VIEW ON GITHUB');

    const link = button.closest('a');

    expect(button).toBeInTheDocument();
    expect(link).toHaveAttribute('href', 'https://github.com/toolchaindev/toolchain/');

    scope.done();
  });

  it('should render sample username as filter chip when clicking my builds tab', async () => {
    const response: BuildsListResponse = {
      results: buildsListMock,
      total_pages: 3,
      max_pages: 3,
      page: 1,
    };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(100)
      .query({ user: 'me', page: 1 })
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ user: 'me', page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds(null, sampleUser);

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    fireEvent.click(screen.queryByTitle('My Builds'));

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.getByText(`User ${sampleUser.username}`)).toBeInTheDocument();

    scope.done();
  });

  it('should render render loading while user list are being loaded (in chip)', async () => {
    const queryObj = { user: users[0].username };
    const queryString = qs.stringify(queryObj);
    const response: BuildsListResponse = {
      results: buildsListMock,
      total_pages: 3,
      max_pages: 3,
      page: 1,
    };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(100)
      .query({ user: users[0].username, page: 1 })
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1, user: users[0].username })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds(queryString);

    expect(screen.getByText('User loading...')).toBeInTheDocument();

    await waitFor(() => expect(screen.queryByText('User loading...')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.getByText(`User ${users[0].username}`)).toBeInTheDocument();

    scope.done();
  });

  it('should load more builds on load more click (from next page)', async () => {
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, {
        results: [buildsListMock[0], buildsListMock[1]],
        total_pages: 30,
        page: 1,
      })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(100)
      .query({ page: 2 })
      .reply(200, {
        results: [buildsListMock[2], buildsListMock[3]],
        total_pages: 30,
        page: 2,
      })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(100)
      .query({ page: 3 })
      .reply(200, {
        results: [buildsListMock[4], buildsListMock[5]],
        total_pages: 30,
        page: 3,
      })
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 2 })
      .delay(100)
      .reply(200, { indicators: {} })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 3 })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    const table = await screen.findByRole('grid');

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    const firstPageRows = table.querySelectorAll('tbody tr');

    // A table row contains two tr's (one for the row itself and one for the spacer)
    expect(firstPageRows).toHaveLength(4);

    fireEvent.click(screen.queryByText(/load more/i));

    await screen.findByText(/loading/i);

    await waitFor(() => expect(screen.queryByText(/loading/i)).not.toBeInTheDocument());

    const secondPageRows = table.querySelectorAll('tbody tr');

    expect(secondPageRows).toHaveLength(8);

    fireEvent.click(screen.queryByText(/load more/i));

    await screen.findByText(/loading/i);

    await waitFor(() => expect(screen.queryByText(/loading/i)).not.toBeInTheDocument());

    const thirdPageRows = table.querySelectorAll('tbody tr');

    expect(thirdPageRows).toHaveLength(12);

    await waitFor(() => expect(screen.queryByText(/data loading.../i)).not.toBeInTheDocument());

    scope.done();
  });

  it('should display all builds loaded if total_pages === current page', async () => {
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, {
        results: [buildsListMock[0], buildsListMock[1]],
        count: 11,
        total_pages: 3,
        max_pages: 3,
      })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(100)
      .query({ page: 2 })
      .reply(200, {
        results: [buildsListMock[2], buildsListMock[3]],
        count: 18,
        total_pages: 3,
        max_pages: 3,
      })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(100)
      .query({ page: 3 })
      .reply(200, {
        results: [buildsListMock[4], buildsListMock[5]],
        count: 22,
        total_pages: 3,
        max_pages: 3,
      })
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 2 })
      .delay(100)
      .reply(200, { indicators: {} })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 3 })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    await screen.findByRole('grid');

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    fireEvent.click(screen.queryByText(/load more/i));

    await screen.findByText(/loading/i);

    await waitFor(() => expect(screen.queryByText(/loading/i)).not.toBeInTheDocument());

    fireEvent.click(screen.queryByText(/load more/i));

    await screen.findByText(/loading/i);

    await waitFor(() => expect(screen.queryByText(/loading/i)).not.toBeInTheDocument());

    expect(screen.queryByText(/load more/i)).not.toBeInTheDocument();
    expect(screen.getByText(/All builds are loaded/i)).toBeInTheDocument();
    expect(screen.getByText(/back to top/i)).toBeInTheDocument();

    await waitFor(() => expect(screen.queryByText(/data loading.../i)).not.toBeInTheDocument());

    scope.done();
  });

  it('should display all builds loaded if total_pages === 0', async () => {
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, {
        results: [buildsListMock[0], buildsListMock[1]],
        total_pages: 0,
      })
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    await screen.findByRole('grid');

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.queryByText(/load more/i)).not.toBeInTheDocument();
    expect(screen.getByText(/All builds are loaded/i)).toBeInTheDocument();
    expect(screen.getByText(/back to top/i)).toBeInTheDocument();

    scope.done();
  });

  it('should load autocomplete values for pr number and apply filter successfully', async () => {
    const response: BuildsListResponse = { results: buildsListMock, total_pages: 3, max_pages: 3, page: 1 };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1, pr: prNumbers[0] })
      .delay(100)
      .reply(200, { ...response, results: [buildsListMock[0], buildsListMock[1]] })
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1, pr: 200 })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    await screen.findByRole('grid');

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.queryByText('Filters')).toBeNull();

    fireEvent.click(screen.getByLabelText('show filters'));

    expect(screen.getByText('Filters')).toBeInTheDocument();

    fireEvent.input(screen.queryByLabelText('Pull request'), { target: { value: '1333' } });

    await screen.findByRole('listbox');

    fireEvent.click(screen.queryByText(prNumbers[0]));

    await waitFor(() => expect(screen.queryByLabelText('Pull request')).toHaveValue(prNumbers[0]));

    fireEvent.click(screen.queryByText('APPLY FILTERS'));

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    await screen.findByText(`Pull request: #${prNumbers[0]}`);

    scope.done();
  });

  it('should render 404 if orgSlug does not belong to the current user', async () => {
    const scope = nock(TESTING_HOST)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: [orgs[1]], prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} });

    renderListBuilds();

    await screen.findByText(/404/);

    scope.done();
  });

  it('should render 404 if repoSlug does not belong to the current user', async () => {
    const scope = nock(TESTING_HOST)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, [repos[1]])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} });

    renderListBuilds();

    await screen.findByText(/404/);

    scope.done();
  });

  it('should load autocomplete values for title and apply filter successfully', async () => {
    const response: BuildsListResponse = { results: buildsListMock, total_pages: 3, max_pages: 3, page: 1 };
    const suggestResponse = {
      values: [
        'Add PR title to PullRequestInfo (#8741)',
        'Add test for buildsense API bug',
        'Add test for buildsense API bug (#8752)',
      ],
    };
    const value = 'add';

    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1, title: suggestResponse.values[0] })
      .delay(100)
      .reply(200, { ...response, results: [buildsListMock[0], buildsListMock[1]] })
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1, title: suggestResponse.values[0] })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/suggest/')
      .query({ q: value })
      .delay(100)
      .reply(200, suggestResponse)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/suggest/')
      .query({ q: suggestResponse.values[0] })
      .delay(100)
      .reply(200, { values: [] });

    renderListBuilds();

    await screen.findByRole('grid');

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.queryByText('Filters')).toBeNull();

    fireEvent.click(screen.getByLabelText('show filters'));

    await screen.findByText('Filters');

    jest.useFakeTimers();

    fireEvent.change(screen.getByRole('combobox', { name: /title/i }), { target: { value } });

    await waitFor(() => expect(screen.getByRole('combobox', { name: /title/i })).toHaveValue(value));

    act(() => jest.runAllTimers());

    await screen.findByRole('listbox');

    jest.useRealTimers();

    suggestResponse.values.forEach(val => expect(screen.getByText(val)).toBeInTheDocument());

    fireEvent.click(screen.queryByText(suggestResponse.values[0]));

    await waitFor(() => expect(screen.queryByRole('listbox')).not.toBeInTheDocument);

    await waitFor(() => expect(screen.queryByLabelText('Title')).toHaveValue(suggestResponse.values[0]));

    fireEvent.click(screen.queryByText('APPLY FILTERS'));

    await screen.findByText('Loading builds...');

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.getByText(`Title: ${suggestResponse.values[0]}`)).toBeInTheDocument();

    scope.done();
  });

  it('should render current user filter as user select box value', async () => {
    const queryObj = { page: 1, user: users[2].username };
    const queryString = qs.stringify(queryObj);
    const response: BuildsListResponse = {
      results: buildsListMock,
      total_pages: 3,
      max_pages: 3,
      page: 1,
    };

    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ ...queryObj })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ ...queryObj })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds(queryString);

    await screen.findByRole('grid');

    await waitFor(() => expect(screen.queryByText('User loading...')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.getByText(`User ${users[2].username}`)).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('show filters'));

    expect(screen.queryByLabelText('User')).toHaveValue(users[2].username);

    scope.done();
  });

  it('should render view on bitbucket button and link', async () => {
    const response: BuildsListResponse = {
      results: buildsListMock,
      total_pages: 3,
      max_pages: 3,
      page: 1,
    };

    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, [{ ...repos[0], scm: 'bitbucket', repo_link: 'https://bitbucket.org/toolchaindev/toolchain/' }])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    const button = await screen.findByText('VIEW ON BITBUCKET');
    const link = button.closest('a');

    expect(button).toBeInTheDocument();
    expect(link).toHaveAttribute('href', 'https://bitbucket.org/toolchaindev/toolchain/');

    scope.done();
  });

  it('should render cache hit rate', async () => {
    const response: BuildsListResponse = {
      results: [buildsListMock[0]],
      total_pages: 3,
      max_pages: 3,
      page: 1,
    };

    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: { ...buildsListMock[13].indicators } })
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    await screen.findByRole('grid');

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    await screen.findByText('50% from cache');

    scope.done();
  });

  it('should not render cache hit rate', async () => {
    const response: BuildsListResponse = {
      results: [buildsListMock[0]],
      total_pages: 3,
      max_pages: 3,
      page: 1,
    };

    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    await screen.findByRole('grid');

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.queryByText('50% from cache')).not.toBeInTheDocument();

    scope.done();
  });

  it('should not render error message for indication call', async () => {
    const response: BuildsListResponse = {
      results: [buildsListMock[0]],
      total_pages: 3,
      max_pages: 3,
      page: 1,
    };

    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(500, {
        details: 'Error during API request',
      })
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    await screen.findByRole('grid');

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.queryByText('Error handling request.')).not.toBeInTheDocument();

    scope.done();
  });

  it('should not apply runtime filter by default', async () => {
    const response: BuildsListResponse = { results: buildsListMock, total_pages: 3, max_pages: 3, page: 1 };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1, pr: '1333' })
      .delay(100)
      .reply(200, { results: [], prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1, pr: '1333' })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    const { history } = renderListBuilds();

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    fireEvent.click(screen.queryByLabelText('show filters'));

    expect(screen.getByText('Filters')).toBeInTheDocument();

    fireEvent.input(screen.queryByLabelText('Pull request'), { target: { value: '1333' } });

    fireEvent.click(screen.queryByText('APPLY FILTERS'));

    await screen.findByText('Loading builds...');

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(history.location.search).toBe('?pr=1333');
    expect(history.location.search).not.toContain('run_time');

    scope.done();
  });

  it('should successfully sort elements', async () => {
    const response: BuildsListResponse = { results: buildsListMock, total_pages: 3, max_pages: 3, page: 1 };
    const queryObj1 = { sort: 'timestamp' };
    const queryObj2 = { sort: '-timestamp' };

    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(100)
      .query({ ...queryObj1, page: 1 })
      .reply(200, response)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ ...queryObj1, page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(100)
      .query({ ...queryObj2, page: 1 })
      .reply(200, response)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ ...queryObj2, page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    fireEvent.click(screen.getByText('STARTED'));

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.getByText('sorted ascending'));

    fireEvent.click(screen.getByText('STARTED'));

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.getByText('sorted descending'));

    scope.done();
  });

  it('should not show loading message while still fetching indicators', async () => {
    const response: BuildsListResponse = { results: buildsListMock, total_pages: 3, max_pages: 3, page: 1 };

    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(1000)
      .reply(200, { indicators: { ...buildsListMock[13].indicators } })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    await screen.findByRole('grid');

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    // no loading state and no cache
    expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument();
    expect(screen.queryByText('50% from cache')).not.toBeInTheDocument();

    await screen.findByText('50% from cache');

    scope.done();
  });

  it('should refetch indicators on new page load', async () => {
    const response: BuildsListResponse = {
      results: [buildsListMock[0], buildsListMock[1]],
      total_pages: 3,
      max_pages: 3,
      page: 1,
    };
    const responsePageTwo: BuildsListResponse = {
      results: [buildsListMock[2], buildsListMock[3]],
      total_pages: 3,
      max_pages: 3,
      page: 2,
    };

    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 2 })
      .delay(100)
      .reply(200, responsePageTwo)
      .get('/api/v1/users/repos/')
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: { ...buildsListMock[13].indicators } })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 2 })
      .delay(500)
      .reply(200, { indicators: { ...buildsListMock[14].indicators } })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    await screen.findByRole('grid');

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.getByText('50% from cache')).toBeInTheDocument();

    fireEvent.click(screen.queryByText(/load more/i));

    await screen.findByText(/loading/i);

    await waitFor(() => expect(screen.queryByText(/data loading.../i)).not.toBeInTheDocument());

    await screen.findByText(/data loading.../i);

    await waitFor(() => expect(screen.queryByText(/loading/i)).not.toBeInTheDocument());

    expect(screen.getByText('25% from cache')).toBeInTheDocument();

    scope.done();
  });

  it('should render free trial banner', async () => {
    const response: BuildsListResponse = {
      results: buildsListMock,
      total_pages: 3,
      max_pages: 3,
      page: 1,
    };

    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    await screen.findByRole('grid');

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(
      screen.getByText(`${org} is in free trial. Upgrade to continue using the service at the end of the trial.`)
    ).toBeInTheDocument();
    expect(screen.getByText(/see plans/i)).toBeInTheDocument();

    scope.done();
  });

  it('should render no builds banner', async () => {
    const response: BuildsListResponse = {
      results: [],
      total_pages: 0,
      max_pages: 0,
      page: 1,
    };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        status: 'no_builds',
        docs: 'link_to_docs',
      });
    renderListBuilds();

    await screen.findByRole('grid');

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.getByText(/to start running builds in this repo, please finish the setup./i)).toBeInTheDocument();
    expect(screen.getByText(/instructions/i)).toBeInTheDocument();

    scope.done();
  });

  it('should not show retry snackbar for indicators call after retrying', async () => {
    const response: BuildsListResponse = {
      results: [],
      total_pages: 3,
      max_pages: 3,
      page: 1,
    };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchaindev/toolchain/builds/')
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get('/api/v1/repos/toolchaindev/toolchain/builds/indicators/')
      .times(5)
      .query({ page: 1 })
      .delay(100)
      .reply(502, undefined)
      .options('/api/v1/repos/toolchaindev/toolchain/builds/')
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderListBuilds();

    await screen.findByRole('grid');

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.getByText(/data loading.../i)).toBeInTheDocument();

    await waitFor(() => expect(screen.queryByText(/data loading.../i)).not.toBeInTheDocument(), { timeout: 20000 });

    await screen.findByText(/data not available/i);

    expect(screen.queryByText(/service unavailable at the moment/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/retry/i)).not.toBeInTheDocument();

    scope.done();
  }, 20000);
});
