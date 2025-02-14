/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';
import nock from 'nock';
import MockDate from 'mockdate';
import { QueryClientProvider } from '@tanstack/react-query';

import OrganizationPage from 'pages/organization/organization';
import NoOrganizationsPage from 'pages/no-organizations/no-organizations';
import RedirectToOrganizationPage from 'components/redirect-to-organization/redirect-to-organizations';

import organizations, { organization, organizationPlanEnterprise } from '../../../tests/__fixtures__/orgs';
import render from '../../../tests/custom-render';
import queryClient from '../../../tests/queryClient';

const TESTING_HOST = 'http://localhost';

jest.mock('utils/datetime-formats', () => ({
  ...Object.assign(jest.requireActual('utils/datetime-formats')),
  dateTimeToLocal: (value: any) => value,
}));
jest.mock('utils/init-data', () => ({
  getHost: () => TESTING_HOST,
}));
jest.mock('../../utils/hooks/access-token');

const renderRedirectToOrganization = () =>
  render(
    <QueryClientProvider client={queryClient}>
      <Routes>
        <Route path="/" element={<RedirectToOrganizationPage />} />
        <Route path="/no-organizations/" element={<NoOrganizationsPage />} />
        <Route path="/organizations/:orgSlug" element={<OrganizationPage />} />
      </Routes>
    </QueryClientProvider>,
    { wrapperProps: { pathname: '/' } }
  );

describe('<RedirectToOrganizations />', () => {
  beforeEach(() => {
    MockDate.set(new Date('2019-05-14T11:01:58.135Z'));
    queryClient.clear();
    nock.cleanAll();
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

  it('should render no-organizations component if there is no organizations connected to the user account', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/users/me/customers/`)
      .delay(100)
      .reply(200, { results: [], prev: null, next: null });

    renderRedirectToOrganization();

    await screen.findByText('You are not in any organization');

    expect(screen.getByText('You are not in any organization')).toBeInTheDocument();

    scope.done();
  });

  it('should render organization component if there is any organizations connected to the user account', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/users/me/customers/`)
      .delay(100)
      .reply(200, { results: organizations, prev: null, next: null })
      .get(`/api/v1/customers/${organizations[0].slug}/`)
      .delay(20)
      .reply(200, organization)
      .get(`/api/v1/customers/${organizations[0].slug}/plan/`)
      .delay(50)
      .reply(200, organizationPlanEnterprise);

    renderRedirectToOrganization();

    await waitFor(() => {
      expect(screen.getByText('Repositories')).toBeInTheDocument();
    });

    await screen.findByText('Enterprise');

    scope.done();
  });
});
