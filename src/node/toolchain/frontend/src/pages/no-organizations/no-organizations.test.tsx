/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';

import { waitFor, screen } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import nock from 'nock';
import MockDate from 'mockdate';

import OrganizationPage from 'pages/organization/organization';
import NoOrganizationsPage from 'pages/no-organizations/no-organizations';
import RedirectToOrganizationPage from 'components/redirect-to-organization/redirect-to-organizations';
import paths from 'utils/paths';

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

const renderNoOrganizationsPage = (pathname = '/', state: { fromRedirect: boolean } = { fromRedirect: true }) =>
  render(
    <QueryClientProvider client={queryClient}>
      <Routes>
        <Route path="/" element={<RedirectToOrganizationPage />} />
        <Route path="/no-organizations/" element={<NoOrganizationsPage />} />
        <Route path="/organizations/:orgSlug" element={<OrganizationPage />} />
      </Routes>
    </QueryClientProvider>,
    { wrapperProps: { pathname, state } }
  );

describe('<NoOrganizationsPage />', () => {
  beforeEach(() => {
    MockDate.set(new Date('2019-05-14T11:01:58.135Z'));
    queryClient.clear();
    nock.cleanAll();
  });

  afterEach(() => {
    queryClient.clear();
    nock.cleanAll();
  });

  afterAll(() => {
    nock.restore();
    nock.cleanAll();
    queryClient.clear();
    MockDate.reset();
    jest.clearAllMocks();
  });

  it('should render no-organizations', async () => {
    const { asFragment } = renderNoOrganizationsPage(paths.noOrganization);

    await screen.findByText('You are not in any organization');

    expect(asFragment()).toMatchSnapshot();
  });

  it('should redirect to no organization when no orgs in response', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: [], next: null, prev: null });

    const { asFragment } = renderNoOrganizationsPage();

    await screen.findByText('You are not in any organization');

    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should redirect to first organization when orgs are present in response', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${organizations[0].slug}/`)
      .delay(20)
      .reply(200, organization)
      .get(`/api/v1/customers/${organizations[0].slug}/plan/`)
      .delay(50)
      .reply(200, organizationPlanEnterprise);

    renderNoOrganizationsPage('/', { fromRedirect: false });

    await waitFor(() => {
      expect(screen.getByText('Repositories')).toBeInTheDocument();
    });

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    scope.done();
  });
});
