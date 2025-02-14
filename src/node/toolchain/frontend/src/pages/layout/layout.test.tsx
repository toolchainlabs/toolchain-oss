/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { Route, Routes } from 'react-router-dom';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import userEvent from '@testing-library/user-event';
import nock from 'nock';

import OrganizationPage from 'pages/organization/organization';
import NotFound from 'pages/not-found';
import HomePage from 'pages/home-page';
import UserTokens from 'pages/users/tokens';
import generateUrl from 'utils/url';
import backendPaths from 'utils/backend-paths';
import { getHost } from 'utils/init-data';
import UserProfile from 'pages/users/profile';
import Layout from './layout';
import createMatchMedia from '../../../tests/createMatchMedia';
import tokens from '../../../tests/__fixtures__/tokens';
import { organization, organizationPlanEnterprise } from '../../../tests/__fixtures__/orgs';
import render from '../../../tests/custom-render';
import paths from 'utils/paths';
import queryClient from '../../../tests/queryClient';

const TESTING_HOST = 'http://localhost';
const MOCK_ACCESS_TOKEN = 'tiJn5VVmT6UDwCpMTpOv';
const assignMock = jest.fn();

jest.mock('utils/init-data', () => ({
  getHost: () => TESTING_HOST,
}));
jest.mock('utils/hooks/access-token');

const orgSlug = 'seinfeldorg';

const mockOrganizations = [
  {
    id: 'org-id-1',
    logo_url: 'http://example.com/avatar-1.png',
    name: 'Jerry Seinfeld Organization',
    slug: 'seinfeldorg',
  },
  {
    id: 'org-id-2',
    logo_url: '',
    name: 'Kramer Organization',
    slug: 'kramerorg',
  },
];

const mockReposData = [
  {
    customer_id: 'org-id-1',
    customer_logo: 'http://example.com/avatar-1.png',
    customer_slug: 'seinfeldorg',
    id: 'opaque-repo-id-1',
    name: 'Repo 1',
    slug: 'repo-one',
  },
  {
    customer_id: 'org-id-1',
    customer_logo: 'http://example.com/avatar-1.png',
    customer_slug: 'seinfeldorg',
    id: 'opaque-repo-id-2',
    name: 'Repo 2',
    slug: 'repo-two',
  },
  {
    customer_id: 'org-id-2',
    customer_logo: '',
    customer_slug: 'kramerorg',
    id: 'opaque-repo-id-50',
    name: 'Repo 50',
    slug: 'repo-fifty',
  },
];

const mockUser = {
  api_id: 'someId',
  avatar_url: 'https://avatars1.githubusercontent.com/u/35751794?s=200&v=4',
  email: 'email',
  username: 'gcostanza',
  full_name: 'George Costanza',
};

const renderLayout = (route = '/') =>
  render(
    <QueryClientProvider client={queryClient}>
      <Layout>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/profile/" element={<UserProfile />} />
          <Route path="/tokens/" element={<UserTokens />} />
          <Route path="/organizations/:orgSlug/" element={<OrganizationPage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Layout>
    </QueryClientProvider>,
    {
      wrapperProps: { pathname: route },
      providerProps: {
        orgAndRepo: {
          initOrg: orgSlug,
          initRepo: null,
        },
      },
    }
  );

describe('Layout', () => {
  const { location } = window;

  beforeAll(() => {
    delete window.location;

    (window.matchMedia as any) = createMatchMedia(window.innerWidth);
    (window.location as any) = { ...location, assign: assignMock };
  });

  beforeEach(() => {
    nock.cleanAll();
    queryClient.clear();
  });

  afterEach(() => jest.clearAllMocks());

  afterAll(() => {
    nock.restore();
    nock.cleanAll();
    queryClient.clear();
    jest.clearAllMocks();
    window.location = location;
  });

  it('should render the home page successfully', async () => {
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, mockUser)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: mockOrganizations, next: null, prev: null })
      .get(`/api/v1/users/repos/`)
      .delay(50)
      .reply(200, mockReposData);

    const { asFragment } = renderLayout();

    await screen.findByLabelText(/open menu/i);

    fireEvent.click(screen.queryByLabelText(/open menu/i));

    await screen.findByText('Jerry Seinfeld Organization');

    await screen.findByText('@gcostanza');

    fireEvent.click(screen.queryByLabelText(/open menu/i));

    await screen.findByText(/Welcome to Toolchain!/);

    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should render organization icons when the sidebar is closed', async () => {
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, mockUser)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: mockOrganizations, next: null, prev: null })
      .get(`/api/v1/users/repos/`)
      .delay(50)
      .reply(200, mockReposData)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(200, organization)
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .delay(50)
      .reply(200, organizationPlanEnterprise);

    renderLayout(paths.organization(orgSlug));

    await screen.findByLabelText(/open menu/i);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(screen.queryByAltText(orgSlug)).toHaveAttribute('src', organization.customer.logo_url);

    await screen.findByText('Enterprise');

    scope.done();
  });

  it('should close error snackbar on menu click', async () => {
    const user = userEvent.setup();
    const error = 'No customers found.';
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, mockUser)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(404, { detail: error })
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(200, organization)
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .delay(50)
      .reply(200, organizationPlanEnterprise);

    renderLayout(paths.organization(orgSlug));

    await screen.findByLabelText(/open menu/i);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText(error);

    user.click(screen.getByLabelText(/open menu/i));

    await waitFor(() => expect(screen.queryByText(error)).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    scope.done();
  });

  it('should render menu icons when the sidebar is closed', async () => {
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, mockUser)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: mockOrganizations, next: null, prev: null })
      .get(`/api/v1/users/repos/`)
      .delay(50)
      .reply(200, mockReposData);

    renderLayout();

    await screen.findByLabelText(/open menu/i);

    fireEvent.click(screen.queryByLabelText(/open menu/i));

    await screen.findByText('Jerry Seinfeld Organization');

    await screen.findByText('@gcostanza');

    fireEvent.click(screen.queryByLabelText(/open menu/i));

    expect(screen.getByLabelText(/open menu/i)).toBeInTheDocument();

    scope.done();
  });

  it('should render username and full_name when sidebar is opened', async () => {
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, mockUser)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: mockOrganizations, next: null, prev: null })
      .get(`/api/v1/users/repos/`)
      .delay(50)
      .reply(200, mockReposData);

    renderLayout();

    await screen.findByLabelText(/open menu/i);

    fireEvent.click(screen.queryByLabelText(/open menu/i));

    await screen.findByText('Jerry Seinfeld Organization');

    expect(screen.getByText('@gcostanza')).toBeInTheDocument();
    expect(screen.getByText('George Costanza')).toBeInTheDocument();

    scope.done();
  });

  it('should show all organization and repository names, and username, when the sidebar is open', async () => {
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, mockUser)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: mockOrganizations, next: null, prev: null })
      .get(`/api/v1/users/repos/`)
      .delay(50)
      .reply(200, mockReposData);

    renderLayout();

    await waitFor(() => {
      expect(screen.getByLabelText(/open menu/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.queryByLabelText(/open menu/i));

    await waitFor(() => {
      expect(screen.getByText('Jerry Seinfeld Organization')).toBeInTheDocument();
    });

    expect(screen.getByText('Kramer Organization')).toBeInTheDocument();
    expect(screen.getByText('Repo 1')).toBeInTheDocument();
    expect(screen.getByText('Repo 2')).toBeInTheDocument();
    expect(screen.getByText('Repo 50')).toBeInTheDocument();
    expect(screen.getByText('@gcostanza')).toBeInTheDocument();

    scope.done();
  });

  it('should close sidebar when the close sidebar button is clicked', async () => {
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, mockUser)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: mockOrganizations, next: null, prev: null })
      .get(`/api/v1/users/repos/`)
      .delay(50)
      .reply(200, mockReposData);

    renderLayout();

    await waitFor(() => {
      expect(screen.getByLabelText(/open menu/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.queryByLabelText(/open menu/i));

    await waitFor(() => {
      expect(screen.getByText('Jerry Seinfeld Organization')).toBeInTheDocument();
    });

    const closeSidebarButton = screen.queryByLabelText('Close drawer');
    fireEvent.click(closeSidebarButton);

    await waitFor(() => expect(screen.queryByText('Kramer Organization')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText('Repo 1')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText('Repo 2')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText('Repo 50')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText('@gcostanza')).not.toBeInTheDocument());

    scope.done();
  });

  it('should close sidebar when the organization button is clicked', async () => {
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, mockUser)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: mockOrganizations, next: null, prev: null })
      .get(`/api/v1/users/repos/`)
      .delay(50)
      .reply(200, mockReposData)
      .get(`/api/v1/customers/${orgSlug}/`)
      .delay(20)
      .reply(200, organization)
      .get(`/api/v1/customers/${orgSlug}/plan/`)
      .delay(50)
      .reply(200, organizationPlanEnterprise);

    renderLayout();

    await waitFor(() => {
      expect(screen.getByLabelText(/open menu/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.queryByLabelText(/open menu/i));

    await waitFor(() => {
      expect(screen.getByText('Jerry Seinfeld Organization')).toBeInTheDocument();
    });

    fireEvent.click(screen.queryByText('Jerry Seinfeld Organization'));

    await waitFor(() => {
      expect(screen.queryByText('@gcostanza')).not.toBeInTheDocument();
    });

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText('Enterprise');

    scope.done();
  });

  it('should close sidebar when the repo button is clicked', async () => {
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, mockUser)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: mockOrganizations, next: null, prev: null })
      .get(`/api/v1/users/repos/`)
      .delay(50)
      .reply(200, mockReposData);

    renderLayout();

    await waitFor(() => {
      expect(screen.getByLabelText(/open menu/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.queryByLabelText(/open menu/i));

    await waitFor(() => {
      expect(screen.getByText('Repo 1')).toBeInTheDocument();
    });

    fireEvent.click(screen.queryByText('Repo 1'));

    await waitFor(() => {
      expect(screen.queryByText('@gcostanza')).not.toBeInTheDocument();
    });

    scope.done();
  });

  it('should navigate to profile successfully', async () => {
    const email = 'email';
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, mockUser)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: mockOrganizations, next: null, prev: null })
      .get(`/api/v1/users/repos/`)
      .delay(50)
      .reply(200, mockReposData)
      .get('/api/v1/users/emails/')
      .delay(20)
      .reply(200, { emails: [email] });

    renderLayout();

    await waitFor(() => {
      expect(screen.getByLabelText(/open menu/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.queryByLabelText(/open menu/i));

    await waitFor(() => {
      expect(screen.getByText('@gcostanza')).toBeInTheDocument();
    });

    const avatarText = screen.queryByText('@gcostanza');

    fireEvent.click(avatarText);

    await waitFor(() => {
      expect(screen.getByText(email)).toBeInTheDocument();
    });

    fireEvent.click(screen.queryByLabelText(/close drawer/i));

    await waitFor(() => {
      expect(screen.queryByText('@gcostanza')).not.toBeInTheDocument();
    });

    expect(screen.getByText(/sign out/i)).toBeInTheDocument();

    scope.done();
  });

  it('should navigate to tokens successfully', async () => {
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, mockUser)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: mockOrganizations, next: null, prev: null })
      .get(`/api/v1/users/repos/`)
      .delay(50)
      .reply(200, mockReposData)
      .get('/api/v1/tokens/')
      .delay(50)
      .reply(200, { max_reached: false, tokens });

    renderLayout();

    await waitFor(() => {
      expect(screen.getByLabelText(/open menu/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.queryByLabelText(/open menu/i));

    await waitFor(() => {
      expect(screen.getByText('@gcostanza')).toBeInTheDocument();
    });

    fireEvent.click(screen.queryByText('Pants client tokens'));

    await waitFor(() => expect(screen.queryByText('Loading tokens...')).not.toBeInTheDocument());

    expect(screen.getByRole('grid')).toBeInTheDocument();

    scope.done();
  });

  it('should open sidebar on profile click (closed)', async () => {
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, mockUser)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: mockOrganizations, next: null, prev: null })
      .get(`/api/v1/users/repos/`)
      .delay(50)
      .reply(200, mockReposData);

    renderLayout();

    await waitFor(() => {
      expect(screen.getByLabelText(/open menu/i)).toBeInTheDocument();
    });

    expect(screen.queryByText('@gcostanza')).not.toBeInTheDocument();

    fireEvent.click(screen.queryByLabelText(/open menu/i));

    await waitFor(() => {
      expect(screen.getByText('Jerry Seinfeld Organization')).toBeInTheDocument();
    });

    expect(screen.getByText('@gcostanza')).toBeInTheDocument();

    scope.done();
  });

  it('should render impersonation', async () => {
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, mockUser)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: mockOrganizations, next: null, prev: null })
      .get(`/api/v1/users/repos/`)
      .delay(50)
      .reply(200, mockReposData);

    const impersonation = {
      expiry: '2021-06-18T17:03:23.188832',
      impersonator_full_name: '',
      impersonator_username: 'chrisjrn',
      user_full_name: '',
      user_username: 'john_clarke',
    };
    const appInitDataElement = document.createElement('script');
    appInitDataElement.id = 'app_init_data';
    appInitDataElement.type = 'text/json';
    appInitDataElement.innerText = btoa(JSON.stringify({ impersonation }));

    document.body.appendChild(appInitDataElement);

    renderLayout();

    await screen.findByLabelText(/open menu/i);

    fireEvent.click(screen.queryByLabelText(/open menu/i));

    await screen.findByText('Jerry Seinfeld Organization');

    await screen.findByText('@gcostanza');

    fireEvent.click(screen.queryByLabelText(/open menu/i));

    await waitFor(() => {
      expect(screen.getByLabelText(/open menu/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/quit ghosting mode/i)).toBeInTheDocument();
    expect(
      screen.getByText(`${impersonation.impersonator_username} is ghosting ${impersonation.user_username}`)
    ).toBeInTheDocument();

    document.body.removeChild(appInitDataElement);

    scope.done();
  });

  it('should call location assign on sign out click', async () => {
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, mockUser)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: mockOrganizations, next: null, prev: null })
      .get(`/api/v1/users/repos/`)
      .delay(50)
      .reply(200, mockReposData);

    renderLayout();

    await waitFor(() => {
      expect(screen.getByLabelText(/open menu/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.queryByLabelText(/open menu/i));

    await waitFor(() => {
      expect(screen.getByText('@gcostanza')).toBeInTheDocument();
    });

    await screen.findByText(/Repo 50/i);

    fireEvent.click(screen.queryByText('Sign out'));

    await waitFor(() => {
      expect(assignMock).toHaveBeenCalledWith(generateUrl(backendPaths.users_ui.LOGOUT, getHost()));
    });

    scope.done();
  });

  it('should render support link', async () => {
    const appInitDataElement = document.createElement('script');
    appInitDataElement.id = 'app_init_data';
    appInitDataElement.type = 'text/json';
    appInitDataElement.innerText = btoa(JSON.stringify({ support_link: 'random.href' }));

    document.body.appendChild(appInitDataElement);

    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, mockUser)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: mockOrganizations, next: null, prev: null })
      .get(`/api/v1/users/repos/`)
      .delay(50)
      .reply(200, mockReposData);

    renderLayout();

    await waitFor(() => {
      expect(screen.getByLabelText(/open menu/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.queryByLabelText(/open menu/i));

    await waitFor(() => {
      expect(screen.getByText('@gcostanza')).toBeInTheDocument();
    });

    await screen.findByText(/Repo 50/i);

    const link = screen.getByText(/report issues/i).closest('a');

    expect(link).toBeInTheDocument();

    expect(screen.getByText(/report issues/i).closest('a')).toHaveAttribute('href', 'random.href');

    // Reset app init data
    document.body.removeChild(appInitDataElement);

    scope.done();
  });

  it('should contain query param user=me in location.search', async () => {
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, mockUser)
      .get(`/api/v1/users/me/customers/`)
      .delay(50)
      .reply(200, { results: mockOrganizations, next: null, prev: null })
      .get(`/api/v1/users/repos/`)
      .delay(50)
      .reply(200, mockReposData);

    const { history } = renderLayout();

    await waitFor(() => {
      expect(screen.getByLabelText(/open menu/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.queryByLabelText(/open menu/i));

    await waitFor(() => {
      expect(screen.getByText('@gcostanza')).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText(/repo 1/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.queryByText(/repo 1/i));

    await waitFor(() => {
      expect(screen.queryByText('@gcostanza')).not.toBeInTheDocument();
    });

    expect(history.location.search).toBe('?user=me');

    scope.done();
  });
});
