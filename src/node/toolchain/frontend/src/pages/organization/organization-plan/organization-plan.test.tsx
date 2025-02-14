/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { Routes, Route } from 'react-router-dom';
import MockDate from 'mockdate';
import nock from 'nock';
import { screen, waitFor } from '@testing-library/react';

import render from '../../../../tests/custom-render';
import OrganizationPlan from './organization-plan';
import {
  organizationPlanEmpty,
  organizationPlanEnterprise,
  organizationPlanStarter,
} from '../../../../tests/__fixtures__/orgs';
import { OrganizationPlanAndUsage } from 'common/interfaces/orgs-repo';
import dayjs from 'dayjs';
import queryClient from '../../../../tests/queryClient';

const TESTING_HOST = 'http://localhost';

const billing = '/api/v1/customers/random/billing/';
const slug = 'toolchaindev';

jest.mock('utils/init-data', () => ({
  getHost: () => TESTING_HOST,
}));
jest.mock('../../../utils/hooks/access-token');

const renderOrganizationPlan = ({
  orgSlug = slug,
  billingUrl = null,
}: Partial<React.ComponentProps<typeof OrganizationPlan>> = {}) =>
  render(
    <Routes>
      <Route
        path="/"
        element={
          <QueryClientProvider client={queryClient}>
            <OrganizationPlan billingUrl={billingUrl} orgSlug={orgSlug} />
          </QueryClientProvider>
        }
      />
    </Routes>,
    { wrapperProps: { pathname: '/' } }
  );

const createModifiedPlan = (daysLeft: number) => {
  const modifyedPlan: OrganizationPlanAndUsage = {
    plan: {
      ...organizationPlanStarter.plan,
      trial_end: dayjs().add(daysLeft, 'day').toString(),
    },
    usage: {
      ...organizationPlanStarter.usage,
    },
  };

  return modifyedPlan;
};

describe('<OrganizationPlan />', () => {
  beforeEach(() => {
    MockDate.set(new Date('2022-08-20T11:01:58.135Z'));
    nock.cleanAll();
    queryClient.clear();
  });

  afterEach(() => {
    MockDate.reset();
  });

  afterAll(() => {
    nock.restore();
    nock.cleanAll();
    queryClient.clear();
    jest.clearAllMocks();
  });

  it('should render starter plan card', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${slug}/plan/`)
      .delay(50)
      .reply(200, organizationPlanStarter);

    const { asFragment } = renderOrganizationPlan();

    expect(screen.getByRole('progressbar')).toBeInTheDocument();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should render enterprise plan card with no billingUrl', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${slug}/plan/`)
      .delay(50)
      .reply(200, organizationPlanEnterprise);

    const { asFragment } = renderOrganizationPlan();

    expect(screen.getByRole('progressbar')).toBeInTheDocument();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should render enterprise plan card with billingUrl', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${slug}/plan/`)
      .delay(50)
      .reply(200, organizationPlanEnterprise);

    const { asFragment } = renderOrganizationPlan({ billingUrl: billing });

    expect(screen.getByRole('progressbar')).toBeInTheDocument();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should render plan not available', async () => {
    const scope = nock(TESTING_HOST).get(`/api/v1/customers/${slug}/plan/`).delay(50).reply(200, organizationPlanEmpty);

    const { asFragment } = renderOrganizationPlan();

    expect(screen.getByRole('progressbar')).toBeInTheDocument();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should display 1 day left text', async () => {
    const modifiedPlan = createModifiedPlan(1);

    const scope = nock(TESTING_HOST).get(`/api/v1/customers/${slug}/plan/`).delay(50).reply(200, modifiedPlan);

    renderOrganizationPlan();

    expect(screen.getByRole('progressbar')).toBeInTheDocument();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(screen.getByText('Trial ends in 1 day')).toBeInTheDocument();

    scope.done();
  });

  it('should display more than 1 days left text', async () => {
    const daysLeft = 3;
    const modifiedPlan = createModifiedPlan(daysLeft);

    const scope = nock(TESTING_HOST).get(`/api/v1/customers/${slug}/plan/`).delay(50).reply(200, modifiedPlan);

    renderOrganizationPlan();

    expect(screen.getByRole('progressbar')).toBeInTheDocument();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(screen.getByText(`Trial ends in ${daysLeft} days`)).toBeInTheDocument();

    scope.done();
  });

  it('should display trial has ended text', async () => {
    const modifiedPlan = createModifiedPlan(-3);

    const scope = nock(TESTING_HOST).get(`/api/v1/customers/${slug}/plan/`).delay(50).reply(200, modifiedPlan);

    renderOrganizationPlan();

    expect(screen.getByRole('progressbar')).toBeInTheDocument();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(screen.getByText('Trial has ended')).toBeInTheDocument();

    scope.done();
  });
});
