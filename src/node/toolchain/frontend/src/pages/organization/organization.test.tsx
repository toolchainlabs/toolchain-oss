/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import nock from 'nock';
import MockDate from 'mockdate';
import { QueryClientProvider } from '@tanstack/react-query';

import OrganizationPage from 'pages/organization/organization';
import NotFound from 'pages/not-found';
import ListBuilds from 'pages/builds/list';
import paths from 'utils/paths';

import repos from '../../../tests/__fixtures__/repos';
import branches from '../../../tests/__fixtures__/branches';
import users from '../../../tests/__fixtures__/users';
import goals from '../../../tests/__fixtures__/goals';
import buildsListMock from '../../../tests/__fixtures__/builds-list';
import { organizationPlanEnterprise } from '../../../tests/__fixtures__/orgs';
import organizations, { organization } from '../../../tests/__fixtures__/orgs';
import render from '../../../tests/custom-render';
import queryClient from '../../../tests/queryClient';

const TESTING_HOST = 'http://localhost';
const sampleUser = {
  api_id: 'efdo01831jd1',
  avatar_url: 'https://avatars1.githubusercontent.com/u/35751794?s=200&v=4',
  full_name: 'Random User',
  email: 'email',
  username: 'random',
};
jest.mock('utils/datetime-formats', () => ({
  ...Object.assign(jest.requireActual('utils/datetime-formats')),
  dateTimeToLocal: (value: any) => value,
}));
jest.mock('utils/init-data', () => ({
  getHost: () => TESTING_HOST,
}));
jest.mock('../../utils/hooks/access-token');

const renderOrganizationPage = (orgSlug: string) =>
  render(
    <QueryClientProvider client={queryClient}>
      <Routes>
        <Route path="/organizations/:orgSlug/" element={<OrganizationPage />} />
        <Route path="/organizations/:orgSlug/repos/:repoSlug/builds/" element={<ListBuilds />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </QueryClientProvider>,
    { wrapperProps: { pathname: paths.organization(orgSlug) }, providerProps: { user: { initUser: sampleUser } } }
  );

describe('<OrganizationPage />', () => {
  const { assign } = window.location;
  const orgSlug = 'toolchaindev';
  beforeAll(() => {
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { assign: jest.fn() },
    });
  });

  beforeEach(() => {
    MockDate.set(new Date('2019-05-14T11:01:58.135Z'));
    queryClient.clear();
    nock.cleanAll();
  });

  afterEach(() => {
    MockDate.reset();
  });

  afterAll(() => {
    nock.restore();
    nock.cleanAll();
    queryClient.clear();
    jest.clearAllMocks();
    window.location.assign = assign;
  });

  it('should render component', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(200, organization)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .delay(50)
      .reply(200, organizationPlanEnterprise);

    const { asFragment } = renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should show loader', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(200, organization)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .delay(50)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(orgSlug);

    await screen.findByRole('progressbar');

    expect(screen.getByRole('progressbar')).toBeInTheDocument();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    scope.done();
  });

  it('should show error', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(403, {
        details: 'Error during API request',
      })
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null });

    const { asFragment } = renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should close error message on click', async () => {
    const user = userEvent.setup();
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(403, {
        details: 'Error during API request',
      })
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .delay(10)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    user.click(document.body);

    await waitFor(() => expect(screen.queryByRole('alert')).toBeNull());

    await screen.findByText('Enterprise');

    scope.done();
  });

  it('should render GitHub install widget with correct link when install link provided', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(50)
      .reply(200, {
        ...organization,
        repos: [],
        metadata: {
          configure_link: null,
          install_link: 'https://mock-github-install-link.github.com',
        },
      })
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null });

    renderOrganizationPage(orgSlug);

    expect(screen.getByRole('progressbar')).toBeInTheDocument();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(screen.getByText(/install toolchain/i)).toBeInTheDocument();
    expect(screen.getByText(/install toolchain/i).closest('a')).toHaveAttribute(
      'href',
      'https://mock-github-install-link.github.com'
    );

    scope.done();
  });

  it('should render no repos message when there are no repos and no github install link', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(50)
      .reply(200, {
        ...organization,
        repos: [],
      })
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .delay(10)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(orgSlug);

    expect(screen.getByRole('progressbar')).toBeInTheDocument();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    expect(
      screen.getByText(/There are no repos in this organization. Please contact the admin to configure it./i)
    ).toBeInTheDocument();

    scope.done();
  });

  it('should render no repos message when there are no repos and no github install link (admin)', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(50)
      .reply(200, {
        ...organization,
        repos: [],
        user: { ...organization.user, is_admin: true },
      })
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .delay(10)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(orgSlug);

    expect(screen.getByRole('progressbar')).toBeInTheDocument();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    expect(screen.getByText(/There are no repos in your GitHub org./i)).toBeInTheDocument();

    scope.done();
  });

  it('should render repository list', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(50)
      .reply(200, organization)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .delay(10)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    expect(screen.getByLabelText('Repositories')).toBeInTheDocument();

    scope.done();
  });

  it('should navigate to builds with user=me active from repo link', async () => {
    const repoSlug = 'toolchain';
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(50)
      .reply(200, organization)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .delay(10)
      .reply(200, organizationPlanEnterprise)
      .get(`/api/v1/users/repos/`)
      .delay(100)
      .reply(200, [repos[0]])
      .get(`/api/v1/repos/${orgSlug}/toolchain/builds/`)
      .query({ page: 1, user: 'me' })
      .delay(100)
      .reply(200, { results: buildsListMock, next: null, prev: null })
      .options(`/api/v1/repos/${orgSlug}/toolchain/builds/`)
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      })
      .get(`/api/v1/repos/${orgSlug}/toolchain/builds/indicators/`)
      .query({ page: 1, user: 'me' })
      .delay(100)
      .reply(200, { indicators: {} });

    renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    fireEvent.click(screen.queryByText(repoSlug));

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(screen.getByRole('grid')).toBeInTheDocument();

    await waitFor(() => expect(screen.queryByText('User loading...')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.getByText('clear all')).toBeInTheDocument();
    expect(screen.getByText(`User ${sampleUser.username}`)).toBeInTheDocument();

    scope.done();
  });

  it('should display organization name', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(50)
      .reply(200, organization)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .delay(10)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    expect(screen.getByText(orgSlug)).toBeInTheDocument();

    scope.done();
  });

  it('should display github image and correct link to github page', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(50)
      .reply(200, organization)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .delay(10)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    const link = screen.getByText('VIEW ON GITHUB').closest('a');

    expect(screen.getByAltText('GitHub link icon')).toBeInTheDocument();

    expect(link).toHaveAttribute('href', `https://github.com/${orgSlug}/`);

    scope.done();
  });

  it('should display bitbucket image and correct link to bitbucket page', async () => {
    const org = 'third-organization';
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${org}/`)
      .delay(20)
      .reply(200, {
        ...organization,
        customer: {
          ...organization.customer,
          customer_link: 'https://bitbucket.org/third-organization/',
          scm: 'bitbucket',
        },
      })
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${org}/plan/`)
      .delay(10)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(org);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    const link = screen.getByText('VIEW ON BITBUCKET').closest('a');

    expect(screen.getByAltText('Bitbucket link icon')).toBeInTheDocument();

    expect(link).toHaveAttribute('href', `https://bitbucket.org/third-organization/`);

    scope.done();
  });

  it('should display 404 if orgSlug does not belong to the current user', async () => {
    const org = 'randomSlug';
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${org}/`)
      .delay(20)
      .reply(404, { details: 'Not found' })
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null });

    renderOrganizationPage('randomSlug');

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText(/404/);

    scope.done();
  });

  it('should not render edit org name icon', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(200, organization)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .delay(10)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    expect(screen.queryByLabelText(/edit org name/i)).not.toBeInTheDocument();

    scope.done();
  });

  it('should render edit org name icon', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(200, { ...organization, user: { ...organization.user, is_admin: true } })
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .delay(10)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(screen.getByLabelText(/edit org name/i)).toBeInTheDocument();

    scope.done();
  });

  it('should edit org name successfully after client side validation', async () => {
    const newName = 'seinfeld';
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(200, { ...organization, user: { ...organization.user, is_admin: true } })
      .patch(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(200, { ...organization, customer: { ...organization.customer, name: newName } })
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .twice()
      .delay(10)
      .reply(200, organizationPlanEnterprise)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: [{ ...organizations[0], name: newName }], next: null, prev: null });

    renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    fireEvent.click(screen.getByLabelText(/edit org name/i));

    const input = screen.getByLabelText(/org-name/i);

    fireEvent.input(input, { target: { value: '' } });

    expect(screen.getByText(/organization name is required./i)).toBeInTheDocument();
    expect(screen.getByLabelText(/save org name/i)).toBeDisabled();

    fireEvent.input(input, { target: { value: 'a' } });

    expect(screen.getByText(/organization name must be at least 2 characters long./i)).toBeInTheDocument();
    expect(screen.getByLabelText(/save org name/i)).toBeDisabled();

    fireEvent.input(input, {
      target: {
        value:
          '111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111',
      },
    });

    expect(screen.getByText(/organization name can't be more than 128 characters long./i)).toBeInTheDocument();
    expect(screen.getByLabelText(/save org name/i)).toBeDisabled();

    fireEvent.input(input, { target: { value: newName } });

    expect(screen.queryByText(/organization name must be at least 2 characters long./i)).not.toBeInTheDocument();
    expect(screen.queryByText(/organization name is required./i)).not.toBeInTheDocument();
    expect(screen.queryByText(/organization name can't be more than 128 characters long./i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByLabelText(/save org name/i));

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText(newName);

    await screen.findByText('Enterprise');

    scope.done();
  });

  it('should fail org name edit and display snackbar error', async () => {
    const error = { details: 'some error' };
    const newName = 'seinfeld';
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(200, { ...organization, user: { ...organization.user, is_admin: true } })
      .patch(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(400, error)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .delay(10)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    fireEvent.click(screen.getByLabelText(/edit org name/i));

    const input = screen.getByLabelText(/org-name/i);

    fireEvent.input(input, { target: { value: newName } });

    fireEvent.click(screen.getByLabelText(/save org name/i));

    await waitFor(() => {
      expect(input).not.toBeDisabled();
    });

    await screen.findByText(/something wrong happened, please try again/i);

    scope.done();
  });

  it('should fail org name edit and display returned error', async () => {
    const error = {
      errors: {
        name: [
          { message: 'name has first error.', code: 'invalid_value' },
          { message: 'name has second error.', code: 'invalid_value' },
        ],
      },
    };
    const newName = 'seinfeld';
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(200, { ...organization, user: { ...organization.user, is_admin: true } })
      .patch(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(400, error)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .delay(10)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    fireEvent.click(screen.getByLabelText(/edit org name/i));

    const input = screen.getByLabelText(/org-name/i);

    fireEvent.input(input, { target: { value: newName } });

    fireEvent.click(screen.getByLabelText(/save org name/i));

    await waitFor(() => {
      expect(input).not.toBeDisabled();
    });

    await screen.findByText(error.errors.name.map((err: { message: string; code: string }) => err.message).join(' '));

    scope.done();
  });

  it('should render inactive repo with message', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(200, { ...organization, repos: [{ ...organization.repos[0], is_active: false }] })
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .delay(10)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    expect(screen.getByText(/inactive repo/i)).toBeInTheDocument();

    scope.done();
  });

  it('should render manage plan button disabled and tooltip', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(200, organization)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .delay(10)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    expect(screen.getByText(/manage plan/i).closest('button')).toBeDisabled();

    fireEvent.mouseOver(screen.getByText(/manage plan/i));

    await screen.findByText(/admin access/i);
    await screen.findByText(/only admin users can manage the subscription plan./i);

    scope.done();
  });

  it('should redirect to stripe on manage plan button click', async () => {
    const billingUrl = `/api/v1/customers/${orgSlug}/billing/`;
    const stripeUrl = 'https://billing.stripe.com/session/test';
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(200, { ...organization, customer: { ...organization.customer, billing: billingUrl } })
      .post(billingUrl)
      .delay(20)
      .reply(200, { session_url: stripeUrl })
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .delay(10)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    expect(screen.getByText(/manage plan/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText(/manage plan/i));

    await waitFor(() => expect(window.location.assign).toHaveBeenCalledWith(stripeUrl));

    scope.done();
  });

  it('should show toaster with server side error if there is one', async () => {
    const billingUrl = `/api/v1/customers/${orgSlug}/billing/`;
    const billingError = 'Invalid value for some header';
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(200, { ...organization, customer: { ...organization.customer, billing: billingUrl } })
      .post(billingUrl)
      .delay(20)
      .reply(400, { detail: billingError })
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .delay(10)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    expect(screen.getByText(/manage plan/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText(/manage plan/i));

    await waitFor(() => expect(screen.getByText(/manage plan/i).closest('button')).not.toBeDisabled());

    await screen.findByText(billingError);

    expect(screen.getByText(billingError)).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('close'));

    expect(screen.queryByText(billingError)).not.toBeInTheDocument();

    scope.done();
  });

  it('should render free_trial banner', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(200, { ...organization, repos: [{ ...organization.repos[0], is_active: false }] })
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .delay(10)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    expect(
      screen.getByText(
        `${organization.customer.name} is in free trial. Upgrade to continue using the service at the end of the trial.`
      )
    ).toBeInTheDocument();
    expect(screen.getByText(/see plans/i)).toBeInTheDocument();

    scope.done();
  });

  it('should display activate on hover and successfully activate repo', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(200, {
        ...organization,
        repos: [{ ...organization.repos[0], is_active: false }],
        user: { ...organization.user, is_admin: true },
      })
      .post(`/api/v1/customers/${orgSlug}/repos/${organization.repos[0].slug}/`)
      .delay(20)
      .reply(201, { repo: { ...organization.repos[0], is_active: true } })
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .twice()
      .delay(10)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    expect(screen.queryByText(/activate/i)).not.toBeInTheDocument();

    fireEvent.mouseEnter(screen.getByText('toolchain'));

    expect(screen.getByText(/activate/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText(/activate/i));

    expect(screen.getByText(/you are about to activate this repo/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText('ACTIVATE'));

    await waitFor(() => expect(screen.queryByText('ACTIVATE')).not.toBeInTheDocument());

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    fireEvent.mouseEnter(screen.getByText('toolchain'));

    expect(screen.queryByText(/activate/i)).not.toBeInTheDocument();

    scope.done();
  });

  it('should not display activate on hover', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(200, {
        ...organization,
        repos: [{ ...organization.repos[0], is_active: false }],
        user: { ...organization.user, is_admin: false },
      })
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .delay(10)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(screen.queryByText(/activate/i)).not.toBeInTheDocument();

    fireEvent.mouseEnter(screen.getByText('toolchain'));

    expect(screen.queryByText(/activate/i)).not.toBeInTheDocument();

    scope.done();
  });

  it('should successfully activate repo', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(200, {
        ...organization,
        repos: [{ ...organization.repos[0], is_active: false }],
        user: { ...organization.user, is_admin: true },
      })
      .post(`/api/v1/customers/${orgSlug}/repos/${organization.repos[0].slug}/`)
      .delay(20)
      .reply(201, { repo: { ...organization.repos[0], is_active: true } })
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .thrice()
      .delay(10)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    expect(screen.getByText(/manage repos/i)).toBeInTheDocument();

    expect(screen.queryByText(/activate/i)).not.toBeInTheDocument();

    expect(screen.getByText(/inactive repo/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText(/manage repos/i));

    expect(screen.queryByText(/manage repos/i)).not.toBeInTheDocument();

    expect(screen.getByText(/activate/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText(/activate/i));

    expect(screen.getByText(/you are about to activate this repo/i)).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('activate repo'));

    await waitFor(() => expect(screen.queryByLabelText('activate repo')).not.toBeInTheDocument());

    expect(screen.getByText(/done/i)).toBeInTheDocument();

    expect(screen.queryByText('ACTIVATE')).not.toBeInTheDocument();

    expect(screen.getByText('DEACTIVATE')).toBeInTheDocument();

    await screen.findByText('Enterprise');

    scope.done();
  });

  it('should successfully deactivate repo', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(200, {
        ...organization,
        repos: [{ ...organization.repos[0], is_active: true }],
        user: { ...organization.user, is_admin: true },
      })
      .delete(`/api/v1/customers/${orgSlug}/repos/${organization.repos[0].slug}/`)
      .delay(20)
      .reply(201, { repo: { ...organization.repos[0], is_active: false } })
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .thrice()
      .delay(20)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    expect(screen.getByText(/manage repos/i)).toBeInTheDocument();

    expect(screen.queryByText(/deactivate/i)).not.toBeInTheDocument();

    expect(screen.queryByText(/inactive repo/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByText(/manage repos/i));

    expect(screen.queryByText(/manage repos/i)).not.toBeInTheDocument();

    expect(screen.getByText(/deactivate/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText(/deactivate/i));

    expect(screen.getByText(/you are about to deactivate this repo/i)).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('deactivate repo'));

    await waitFor(() => expect(screen.queryByLabelText('deactivate repo')).not.toBeInTheDocument());

    expect(screen.getByText(/done/i)).toBeInTheDocument();

    expect(screen.queryByText('DEACTIVATE')).not.toBeInTheDocument();

    expect(screen.getByText('ACTIVATE')).toBeInTheDocument();

    await screen.findByText('Enterprise');

    scope.done();
  });

  it('should fail repo activation with server message', async () => {
    const errorMessage = 'Repo activation failed for reason x';
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(200, {
        ...organization,
        repos: [{ ...organization.repos[0], is_active: false }],
        user: { ...organization.user, is_admin: true },
      })
      .post(`/api/v1/customers/${orgSlug}/repos/${organization.repos[0].slug}/`)
      .delay(20)
      .reply(400, { detail: errorMessage })
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .twice()
      .delay(20)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    expect(screen.getByText(/manage repos/i)).toBeInTheDocument();

    expect(screen.queryByText(/activate/i)).not.toBeInTheDocument();

    expect(screen.getByText(/inactive repo/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText(/manage repos/i));

    expect(screen.queryByText(/manage repos/i)).not.toBeInTheDocument();

    expect(screen.getByText(/activate/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText(/activate/i));

    expect(screen.getByText(/you are about to activate this repo/i)).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('activate repo'));

    await screen.findByText(errorMessage);

    await screen.findByText('Enterprise');

    scope.done();
  });

  it('should fail repo activation with generic message', async () => {
    const errorMessage = 'Repo activation failed';
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(200, {
        ...organization,
        repos: [{ ...organization.repos[0], is_active: false }],
        user: { ...organization.user, is_admin: true },
      })
      .post(`/api/v1/customers/${orgSlug}/repos/${organization.repos[0].slug}/`)
      .delay(20)
      .reply(400, undefined)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .twice()
      .delay(20)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    expect(screen.getByText(/manage repos/i)).toBeInTheDocument();

    expect(screen.queryByText(/activate/i)).not.toBeInTheDocument();

    expect(screen.getByText(/inactive repo/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText(/manage repos/i));

    expect(screen.queryByText(/manage repos/i)).not.toBeInTheDocument();

    expect(screen.getByText(/activate/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText(/activate/i));

    expect(screen.getByText(/you are about to activate this repo/i)).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('activate repo'));

    await screen.findByText(errorMessage);

    await screen.findByText('Enterprise');

    scope.done();
  });

  it('should fail repo deactivation with server message', async () => {
    const errorMessage = 'Repo deactivation failed for reason x';
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(200, {
        ...organization,
        repos: [{ ...organization.repos[0], is_active: true }],
        user: { ...organization.user, is_admin: true },
      })
      .delete(`/api/v1/customers/${orgSlug}/repos/${organization.repos[0].slug}/`)
      .delay(20)
      .reply(400, { detail: errorMessage })
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .twice()
      .delay(20)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    expect(screen.getByText(/manage repos/i)).toBeInTheDocument();

    expect(screen.queryByText(/deactivate/i)).not.toBeInTheDocument();

    expect(screen.queryByText(/inactive repo/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByText(/manage repos/i));

    expect(screen.queryByText(/manage repos/i)).not.toBeInTheDocument();

    expect(screen.getByText(/deactivate/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText(/deactivate/i));

    expect(screen.getByText(/you are about to deactivate this repo/i)).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('deactivate repo'));

    await screen.findByText(errorMessage);

    scope.done();
  });

  it('should fail repo deactivation with generic message', async () => {
    const errorMessage = 'Repo deactivation failed';
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(200, {
        ...organization,
        repos: [{ ...organization.repos[0], is_active: true }],
        user: { ...organization.user, is_admin: true },
      })
      .delete(`/api/v1/customers/${orgSlug}/repos/${organization.repos[0].slug}/`)
      .delay(20)
      .reply(400, undefined)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: organizations, next: null, prev: null })
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .twice()
      .delay(20)
      .reply(200, organizationPlanEnterprise);

    renderOrganizationPage(orgSlug);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    expect(screen.getByText(/manage repos/i)).toBeInTheDocument();

    expect(screen.queryByText(/deactivate/i)).not.toBeInTheDocument();

    expect(screen.queryByText(/inactive repo/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByText(/manage repos/i));

    expect(screen.queryByText(/manage repos/i)).not.toBeInTheDocument();

    expect(screen.getByText(/deactivate/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText(/deactivate/i));

    expect(screen.getByText(/you are about to deactivate this repo/i)).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('deactivate repo'));

    await screen.findByText(errorMessage);

    scope.done();
  });
});
