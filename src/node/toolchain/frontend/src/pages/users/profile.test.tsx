/*
Copyright 2019 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { Routes, Route } from 'react-router-dom';
import nock from 'nock';

import Layout from 'pages/layout/layout';
import { ToolchainUser } from 'common/interfaces/builds-options';
import UserProfile from './profile';
import render from '../../../tests/custom-render';
import queryClient from '../../../tests/queryClient';

const defaultUser: ToolchainUser = {
  api_id: 'someId',
  avatar_url: 'https://avatars1.githubusercontent.com/u/35751794?s=200&v=4',
  email: 'example@gmail.com',
  username: 'gcostanza',
  full_name: 'George Constanza',
};
const emails = ['sample@gmail.com', 'example@gmail.com'];
const orgSlug = 'toolchain';
const TESTING_HOST = 'http://localhost';
const MOCK_ACCESS_TOKEN = 'tiJn5VVmT6UDwCpMTpOv';

jest.mock('utils/init-data', () => ({
  getHost: () => TESTING_HOST,
}));
jest.mock('utils/hooks/access-token');

const renderUserProfilePage = () =>
  render(
    <Routes>
      <Route
        path="/profile"
        element={
          <QueryClientProvider client={queryClient}>
            <Layout>
              <UserProfile />
            </Layout>
          </QueryClientProvider>
        }
      />
    </Routes>,
    { wrapperProps: { pathname: '/profile' }, providerProps: { orgAndRepo: { initOrg: orgSlug } } }
  );

describe('UserProfile', () => {
  beforeEach(() => {
    nock.cleanAll();
    queryClient.clear();
  });

  afterAll(() => {
    nock.restore();
    nock.cleanAll();
    queryClient.clear();
    jest.clearAllMocks();
  });

  it('should render component', async () => {
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, defaultUser)
      .get('/api/v1/users/emails/')
      .delay(60)
      .reply(200, { emails })
      .get(`/api/v1/users/repos/`)
      .reply(200, [])
      .get(`/api/v1/users/me/customers/`)
      .reply(200, { results: [], next: null, prev: null });

    const { asFragment } = renderUserProfilePage();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText(defaultUser.email);

    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should render loader', async () => {
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, defaultUser)
      .get('/api/v1/users/emails/')
      .delay(60)
      .reply(200, { emails })
      .get(`/api/v1/users/repos/`)
      .reply(200, [])
      .get(`/api/v1/users/me/customers/`)
      .reply(200, { results: [], next: null, prev: null });

    const { asFragment } = renderUserProfilePage();

    await screen.findByRole('progressbar');

    expect(asFragment()).toMatchSnapshot();

    await screen.findByText(defaultUser.email);

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    scope.done();
  });

  it('should render avatar', async () => {
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, defaultUser)
      .get('/api/v1/users/emails/')
      .delay(60)
      .reply(200, { emails })
      .get(`/api/v1/users/repos/`)
      .reply(200, [])
      .get(`/api/v1/users/me/customers/`)
      .reply(200, { results: [], next: null, prev: null });

    renderUserProfilePage();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText(defaultUser.email);

    // Two avatars render one in sidebar and one on profile page
    screen
      .queryAllByAltText('User avatar')
      .forEach(element => expect(element).toHaveAttribute('src', defaultUser.avatar_url));

    scope.done();
  });

  it('should render username', async () => {
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, defaultUser)
      .get('/api/v1/users/emails/')
      .delay(60)
      .reply(200, { emails })
      .get(`/api/v1/users/repos/`)
      .reply(200, [])
      .get(`/api/v1/users/me/customers/`)
      .reply(200, { results: [], next: null, prev: null });

    renderUserProfilePage();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText(defaultUser.email);

    expect(screen.getByText(defaultUser.username)).toBeInTheDocument();

    scope.done();
  });

  it('should render full_name', async () => {
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, defaultUser)
      .get('/api/v1/users/emails/')
      .delay(60)
      .reply(200, { emails })
      .get(`/api/v1/users/repos/`)
      .reply(200, [])
      .get(`/api/v1/users/me/customers/`)
      .reply(200, { results: [], next: null, prev: null });

    renderUserProfilePage();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText(defaultUser.email);

    expect(screen.getByText(defaultUser.full_name)).toBeInTheDocument();

    scope.done();
  });

  it('should render email select with default value', async () => {
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, defaultUser)
      .get('/api/v1/users/emails/')
      .delay(60)
      .reply(200, { emails })
      .get(`/api/v1/users/repos/`)
      .reply(200, [])
      .get(`/api/v1/users/me/customers/`)
      .reply(200, { results: [], next: null, prev: null });

    renderUserProfilePage();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText(defaultUser.email);

    expect(screen.queryByRole('combobox')).toHaveTextContent(defaultUser.email);

    scope.done();
  });

  it('should change email select value on click', async () => {
    const newEmail = 'sample@gmail.com';
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, defaultUser)
      .get('/api/v1/users/emails/')
      .delay(60)
      .reply(200, { emails })
      .get(`/api/v1/users/repos/`)
      .reply(200, [])
      .get(`/api/v1/users/me/customers/`)
      .reply(200, { results: [], next: null, prev: null });

    renderUserProfilePage();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText(defaultUser.email);

    expect(screen.queryByRole('combobox')).toHaveTextContent(defaultUser.email);

    fireEvent.mouseDown(screen.queryByText(defaultUser.email));

    fireEvent.click(screen.queryByText(newEmail));

    await screen.findByText(newEmail);

    expect(screen.queryByRole('combobox')).toHaveTextContent(newEmail);

    scope.done();
  });

  it('should render input with username for value on edit button click', async () => {
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, defaultUser)
      .get('/api/v1/users/emails/')
      .delay(60)
      .reply(200, { emails })
      .get(`/api/v1/users/repos/`)
      .reply(200, [])
      .get(`/api/v1/users/me/customers/`)
      .reply(200, { results: [], next: null, prev: null });

    renderUserProfilePage();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText(defaultUser.email);

    fireEvent.click(screen.queryByLabelText(/edit username/i));

    await screen.findByDisplayValue(defaultUser.username);

    expect(screen.queryByLabelText('username')).toHaveValue(defaultUser.username);

    scope.done();
  });

  it('should render input with fullname for value on edit icon click', async () => {
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, defaultUser)
      .get('/api/v1/users/emails/')
      .delay(60)
      .reply(200, { emails })
      .get(`/api/v1/users/repos/`)
      .reply(200, [])
      .get(`/api/v1/users/me/customers/`)
      .reply(200, { results: [], next: null, prev: null });

    renderUserProfilePage();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText(defaultUser.email);

    fireEvent.click(screen.queryByLabelText(/edit full name/i));

    await screen.findByDisplayValue(defaultUser.full_name);
    await waitFor(() => expect(screen.queryByLabelText(/fullname/i)).toHaveValue());

    scope.done();
  });

  it('should render sign out button', async () => {
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, defaultUser)
      .get('/api/v1/users/emails/')
      .delay(60)
      .reply(200, { emails })
      .get(`/api/v1/users/repos/`)
      .reply(200, [])
      .get(`/api/v1/users/me/customers/`)
      .reply(200, { results: [], next: null, prev: null });

    renderUserProfilePage();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText(defaultUser.email);

    expect(screen.getByText(/sign out/i)).toBeInTheDocument();

    scope.done();
  });

  it('should render save and cancel buttons when editing', async () => {
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, defaultUser)
      .get('/api/v1/users/emails/')
      .delay(60)
      .reply(200, { emails })
      .get(`/api/v1/users/repos/`)
      .reply(200, [])
      .get(`/api/v1/users/me/customers/`)
      .reply(200, { results: [], next: null, prev: null });

    renderUserProfilePage();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText(defaultUser.email);

    expect(screen.getByText(/sign out/i)).toBeInTheDocument();

    fireEvent.click(screen.queryByLabelText(/edit username/i));

    await waitFor(() => expect(screen.queryByText(/sign out/i)).not.toBeInTheDocument());

    expect(screen.getByText(/cancel/i)).toBeInTheDocument();
    expect(screen.getByText(/save/i)).toBeInTheDocument();

    scope.done();
  });

  it('should cancel edit on cancel button and lose changes', async () => {
    const newUsername = 'randomName';
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, defaultUser)
      .get('/api/v1/users/emails/')
      .delay(60)
      .reply(200, { emails })
      .get(`/api/v1/users/repos/`)
      .reply(200, [])
      .get(`/api/v1/users/me/customers/`)
      .reply(200, { results: [], next: null, prev: null });

    renderUserProfilePage();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText(defaultUser.email);

    fireEvent.click(screen.queryByLabelText(/edit username/i));

    await screen.findByDisplayValue(defaultUser.username);

    expect(screen.queryByLabelText('username')).toHaveValue(defaultUser.username);

    fireEvent.change(screen.queryByLabelText('username'), { target: { value: newUsername } });

    await screen.findByDisplayValue(newUsername);

    expect(screen.queryByLabelText('username')).toHaveValue(newUsername);

    fireEvent.click(screen.queryByText(/cancel/i));

    await waitFor(() => expect(screen.queryByLabelText('username')).not.toBeInTheDocument());

    expect(screen.getByText(defaultUser.username)).toBeInTheDocument();

    fireEvent.click(screen.queryByLabelText(/edit username/i));

    await screen.findByDisplayValue(defaultUser.username);

    expect(screen.queryByLabelText('username')).toHaveValue(defaultUser.username);

    scope.done();
  });

  it('should successfully edit user and update user object', async () => {
    const editedValues = {
      username: 'randomUser',
      full_name: 'Random User',
      email: emails[0],
    };
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, defaultUser)
      .get('/api/v1/users/emails/')
      .delay(60)
      .reply(200, { emails })
      .get(`/api/v1/users/repos/`)
      .reply(200, [])
      .get(`/api/v1/users/me/customers/`)
      .reply(200, { results: [], next: null, prev: null })
      .patch(`/api/v1/users/${defaultUser.api_id}/`, JSON.stringify(editedValues))
      .delay(50)
      .reply(200, { ...defaultUser, ...editedValues });

    renderUserProfilePage();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText(defaultUser.email);

    // Edit username
    fireEvent.click(screen.queryByLabelText(/edit username/i));

    await screen.findByDisplayValue(defaultUser.username);

    expect(screen.queryByLabelText(/username/i)).toHaveValue(defaultUser.username);

    fireEvent.change(screen.queryByLabelText(/username/i), { target: { value: editedValues.username } });

    await screen.findByDisplayValue(editedValues.username);

    expect(screen.queryByLabelText(/username/i)).toHaveValue(editedValues.username);

    // Edit fullname
    fireEvent.click(screen.queryByLabelText(/edit full name/i));

    await screen.findByDisplayValue(defaultUser.full_name);

    expect(screen.queryByLabelText(/fullname/i)).toHaveValue(defaultUser.full_name);

    fireEvent.change(screen.queryByLabelText(/fullname/i), { target: { value: editedValues.full_name } });

    await screen.findByDisplayValue(editedValues.full_name);

    expect(screen.queryByLabelText(/fullname/i)).toHaveValue(editedValues.full_name);

    // Change email
    expect(screen.queryByRole('combobox')).toHaveTextContent(defaultUser.email);

    fireEvent.mouseDown(screen.queryByText(defaultUser.email));

    fireEvent.click(screen.queryByText(editedValues.email));

    await waitFor(() => expect(screen.queryByRole('combobox')).toHaveTextContent(editedValues.email));

    fireEvent.click(screen.queryByText('SAVE'));

    await screen.findByText(/Your profile change has been saved/i);

    // Old values
    expect(screen.queryByRole('combobox')).not.toHaveTextContent(defaultUser.email);
    await waitFor(() => expect(screen.queryByText(defaultUser.username)).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText(defaultUser.full_name)).not.toBeInTheDocument());

    expect(screen.queryByRole('combobox')).toHaveTextContent(editedValues.email);
    expect(screen.getByText(editedValues.username)).toBeInTheDocument();
    expect(screen.getByText(editedValues.full_name)).toBeInTheDocument();
    expect(screen.getByText('Your profile change has been saved')).toBeInTheDocument();

    scope.done();
  });

  it('should return 400 on edit along with validation message from the server', async () => {
    const editedValues = {
      username: 'randomUser;',
      full_name: 'Random User',
      email: 'sample@gmail.com',
    };
    const validationValues: { [key: string]: string[] } = {
      username: ['Enter a valid username. This value may contain only letters, numbers, and @/./+/-/_ characters.'],
      email: ['toolchain user with this email already exists'],
    };
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, defaultUser)
      .get('/api/v1/users/emails/')
      .delay(60)
      .reply(200, { emails })
      .get(`/api/v1/users/repos/`)
      .reply(200, [])
      .get(`/api/v1/users/me/customers/`)
      .reply(200, { results: [], next: null, prev: null })
      .patch(`/api/v1/users/${defaultUser.api_id}/`, JSON.stringify(editedValues))
      .delay(50)
      .reply(400, validationValues);

    renderUserProfilePage();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText(defaultUser.email);

    // Edit username
    fireEvent.click(screen.queryByLabelText(/edit username/i));

    await screen.findByDisplayValue(defaultUser.username);

    expect(screen.queryByLabelText(/username/i)).toHaveValue(defaultUser.username);

    fireEvent.change(screen.queryByLabelText(/username/i), { target: { value: editedValues.username } });

    await screen.findByDisplayValue(editedValues.username);

    expect(screen.queryByLabelText(/username/i)).toHaveValue(editedValues.username);

    // Edit fullname
    fireEvent.click(screen.queryByLabelText(/edit full name/i));

    await screen.findByDisplayValue(defaultUser.full_name);

    expect(screen.queryByLabelText(/fullname/i)).toHaveValue(defaultUser.full_name);

    fireEvent.change(screen.queryByLabelText(/fullname/i), { target: { value: editedValues.full_name } });

    await screen.findByDisplayValue(editedValues.full_name);

    expect(screen.queryByLabelText(/fullname/i)).toHaveValue(editedValues.full_name);

    // Edit email
    fireEvent.mouseDown(screen.queryByText(defaultUser.email));

    fireEvent.click(screen.queryByText(editedValues.email));

    await waitFor(() => expect(screen.queryByRole('combobox')).toHaveTextContent(editedValues.email));

    fireEvent.click(screen.queryByText('SAVE'));

    await waitFor(() => {
      Object.keys(validationValues).forEach(key =>
        validationValues[key].forEach(validation => expect(screen.getByText(validation)).toBeInTheDocument())
      );
    });

    scope.done();
  });

  it('should return 500 and show toast', async () => {
    const editedValues = {
      username: 'randomUser;',
      full_name: 'Random User',
      email: defaultUser.email,
    };
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, defaultUser)
      .get('/api/v1/users/emails/')
      .delay(60)
      .reply(200, { emails })
      .get(`/api/v1/users/repos/`)
      .reply(200, [])
      .get(`/api/v1/users/me/customers/`)
      .reply(200, { results: [], next: null, prev: null })
      .patch(`/api/v1/users/${defaultUser.api_id}/`, JSON.stringify(editedValues))
      .delay(50)
      .reply(500, { details: 'Error handling request' });

    renderUserProfilePage();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText(defaultUser.email);

    // Edit username
    fireEvent.click(screen.queryByLabelText(/edit username/i));

    await screen.findByDisplayValue(defaultUser.username);

    expect(screen.queryByLabelText(/username/i)).toHaveValue(defaultUser.username);

    fireEvent.change(screen.queryByLabelText(/username/i), { target: { value: editedValues.username } });

    await screen.findByDisplayValue(editedValues.username);

    expect(screen.queryByLabelText(/username/i)).toHaveValue(editedValues.username);

    // Edit fullname
    fireEvent.click(screen.queryByLabelText(/edit full name/i));

    await screen.findByDisplayValue(defaultUser.full_name);

    expect(screen.queryByLabelText(/fullname/i)).toHaveValue(defaultUser.full_name);

    fireEvent.change(screen.queryByLabelText(/fullname/i), { target: { value: editedValues.full_name } });

    await screen.findByDisplayValue(editedValues.full_name);

    expect(screen.queryByLabelText(/fullname/i)).toHaveValue(editedValues.full_name);

    fireEvent.click(screen.queryByText('SAVE'));

    await waitFor(() => {
      expect(screen.getByText(/something wrong happened, please try again/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/something wrong happened, please try again/i)).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('close'));

    await waitFor(() =>
      expect(screen.queryByText(/something wrong happened, please try again/i)).not.toBeInTheDocument()
    );

    scope.done();
  });

  it('should validate username (required, length min-max)', async () => {
    const usernameNoValue = '';
    const usernameToShort = 'Ran';
    const userNameToLarge =
      'Lorem ipsum dolor sit amet, consectetur adipisicing elit. Facere debitis sequi aspernatur natus laudantium repellat ratione. Iure velit aspernatur inventore explicabo alias excepturi libero magnam voluptates. Corporis blanditiis nesciunt officia.';
    const validUsername = 'username';
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, defaultUser)
      .get('/api/v1/users/emails/')
      .delay(60)
      .reply(200, { emails })
      .get(`/api/v1/users/repos/`)
      .reply(200, [])
      .get(`/api/v1/users/me/customers/`)
      .reply(200, { results: [], next: null, prev: null });

    renderUserProfilePage();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText(defaultUser.email);

    // Edit username with no length string
    fireEvent.click(screen.queryByLabelText(/edit username/i));

    await screen.findByDisplayValue(defaultUser.username);

    expect(screen.queryByLabelText(/username/i)).toHaveValue(defaultUser.username);

    fireEvent.change(screen.queryByLabelText(/username/i), { target: { value: usernameNoValue } });

    await screen.findByDisplayValue(usernameNoValue);

    expect(screen.queryByLabelText(/username/i)).toHaveValue(usernameNoValue);

    // Required message present and save is disabled
    expect(screen.getByText(/username is required./i)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', {
        name: /save/i,
      })
    ).toBeDisabled();

    // Edit username with to short a string
    fireEvent.change(screen.queryByLabelText(/username/i), { target: { value: usernameToShort } });

    await screen.findByDisplayValue(usernameToShort);

    expect(screen.queryByLabelText(/username/i)).toHaveValue(usernameToShort);

    // To short message present and save is disabled
    expect(screen.getByText(/username must be at least 5 characters./i)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', {
        name: /save/i,
      })
    ).toBeDisabled();

    // Edit username with to long a string
    fireEvent.change(screen.queryByLabelText(/username/i), { target: { value: userNameToLarge } });

    await screen.findByDisplayValue(userNameToLarge);

    expect(screen.queryByLabelText(/username/i)).toHaveValue(userNameToLarge);

    // To long message present and save is disabled
    expect(screen.getByText(/username can't be more than 150 characters./i)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', {
        name: /save/i,
      })
    ).toBeDisabled();

    // Edit username with a valid string
    fireEvent.change(screen.queryByLabelText(/username/i), { target: { value: validUsername } });

    await screen.findByDisplayValue(validUsername);

    expect(screen.queryByLabelText(/username/i)).toHaveValue(validUsername);

    // No validation message present and save is enabled
    expect(screen.queryByText(/username is required./i)).not.toBeInTheDocument();
    expect(screen.queryByText(/username can't be more than 150 characters./i)).not.toBeInTheDocument();
    expect(screen.queryByText(/username is required./i)).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', {
        name: /save/i,
      })
    ).not.toBeDisabled();

    scope.done();
  });

  it('should validate fullName (required, length min-max)', async () => {
    const fullNameNoValue = '';
    const fullNameToShort = 'Ran';
    const fullNameToLarge =
      'Lorem ipsum dolor sit amet, consectetur adipisicing elit. Facere debitis sequi aspernatur natus laudantium repellat ratione. Iure velit aspernatur inventore explicabo alias excepturi libero magnam voluptates. Corporis blanditiis nesciunt officia.';
    const validFullName = 'Valid fullname';
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .get('/api/v1/users/me/')
      .delay(50)
      .reply(200, defaultUser)
      .get('/api/v1/users/emails/')
      .delay(60)
      .reply(200, { emails })
      .get(`/api/v1/users/repos/`)
      .reply(200, [])
      .get(`/api/v1/users/me/customers/`)
      .reply(200, { results: [], next: null, prev: null });

    renderUserProfilePage();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByText(defaultUser.email);

    // Edit fullName with no length string
    fireEvent.click(screen.queryByLabelText(/edit full name/i));

    await screen.findByDisplayValue(defaultUser.full_name);

    expect(screen.queryByLabelText(/fullname/i)).toHaveValue(defaultUser.full_name);

    fireEvent.change(screen.queryByLabelText(/fullname/i), { target: { value: fullNameNoValue } });

    await screen.findByDisplayValue(fullNameNoValue);

    expect(screen.queryByLabelText(/fullname/i)).toHaveValue(fullNameNoValue);

    // Required message present and save is disabled
    expect(screen.getByText(/Name is required./i)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', {
        name: /save/i,
      })
    ).toBeDisabled();

    // Edit fullName with to short a string
    fireEvent.change(screen.queryByLabelText(/fullname/i), { target: { value: fullNameToShort } });

    await screen.findByDisplayValue(fullNameToShort);

    expect(screen.queryByLabelText(/fullname/i)).toHaveValue(fullNameToShort);

    // To short message present and save is disabled
    expect(screen.getByText(/Name must be at least 5 characters./i)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', {
        name: /save/i,
      })
    ).toBeDisabled();

    // Edit fullname with to long a string
    fireEvent.change(screen.queryByLabelText(/fullname/i), { target: { value: fullNameToLarge } });

    await screen.findByDisplayValue(fullNameToLarge);

    expect(screen.queryByLabelText(/fullname/i)).toHaveValue(fullNameToLarge);

    // To long message present and save is disabled
    expect(screen.getByText(/Name can't be more than 150 characters./i)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', {
        name: /save/i,
      })
    ).toBeDisabled();

    // Edit username with a valid string
    fireEvent.change(screen.queryByLabelText(/fullname/i), { target: { value: validFullName } });

    await screen.findByDisplayValue(validFullName);

    expect(screen.queryByLabelText(/fullname/i)).toHaveValue(validFullName);

    // No validation message present and save is enabled
    expect(screen.queryByText(/Name is required./i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Name can't be more than 150 characters./i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Name must be at least 5 characters./i)).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', {
        name: /save/i,
      })
    ).not.toBeDisabled();

    scope.done();
  });
});
