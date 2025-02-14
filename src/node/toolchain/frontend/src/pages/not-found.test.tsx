/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen, fireEvent } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import nock from 'nock';

import NoOrganizationsPage from 'pages/no-organizations/no-organizations';
import RedirectToOrganizationPage from 'components/redirect-to-organization/redirect-to-organizations';
import NotFound from './not-found';
import render from '../../tests/custom-render';
import queryClient from '../../tests/queryClient';

const TESTING_HOST = 'http://localhost';

jest.mock('utils/init-data', () => ({
  getHost: () => TESTING_HOST,
}));

jest.mock('utils/hooks/access-token');

const renderNotFound = () =>
  render(
    <QueryClientProvider client={queryClient}>
      <Routes>
        <Route path="/" element={<RedirectToOrganizationPage />}></Route>
        <Route path="/no-organizations/" element={<NoOrganizationsPage />}></Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
    </QueryClientProvider>,
    { wrapperProps: { pathname: '/random' } }
  );

describe('<NotFound />', () => {
  afterAll(() => {
    nock.cleanAll();
    nock.restore();
    queryClient.clear();
    jest.clearAllMocks();
  });

  it('should render the component', () => {
    const { asFragment } = renderNotFound();

    expect(asFragment()).toMatchSnapshot();
  });

  it(`should render 404`, () => {
    renderNotFound();

    expect(screen.getByText(/404/)).toBeInTheDocument();
  });

  it('should navigate from the 404 page when button is clicked', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/users/me/customers/`)
      .delay(100)
      .reply(200, { results: [], prev: null, next: null });

    renderNotFound();

    fireEvent.click(screen.queryByText('go to homepage'));

    await screen.findByText('You are not in any organization');

    expect(screen.getByText('You are not in any organization')).toBeInTheDocument();

    scope.done();
  });
});
