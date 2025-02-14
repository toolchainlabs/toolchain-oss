/*
Copyright 2019 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { Route, Routes } from 'react-router-dom';
import nock from 'nock';
import MockDate from 'mockdate';

import paths from 'utils/paths';
import Tokens from './tokens';
import sortedTokens from '../../../tests/__fixtures__/tokens';
import render from '../../../tests/custom-render';
import queryClient from '../../../tests/queryClient';

const TESTING_HOST = 'http://localhost';

jest.mock('utils/init-data', () => ({
  getHost: () => TESTING_HOST,
}));
jest.mock('utils/hooks/access-token');

const renderUserTokens = (pathname = paths.tokens) =>
  render(
    <QueryClientProvider client={queryClient}>
      <Routes>
        <Route path="/tokens/" element={<Tokens />} />
      </Routes>
    </QueryClientProvider>,
    { wrapperProps: { pathname } }
  );

describe('<Tokens />', () => {
  let tokens: typeof sortedTokens = [];
  beforeEach(() => {
    nock.cleanAll();
    queryClient.clear();
    tokens = [...sortedTokens];

    MockDate.set(new Date('2019-05-14T11:01:58.135Z'));
  });

  afterAll(() => {
    MockDate.reset();
    nock.cleanAll();
    nock.restore();
    queryClient.clear();
    jest.clearAllMocks();
  });

  it('should render component', async () => {
    const scope = nock(TESTING_HOST).get('/api/v1/tokens/').delay(50).reply(200, { max_reached: false, tokens });
    const { asFragment } = renderUserTokens();

    await waitFor(() => expect(screen.queryByText('Loading tokens...')).not.toBeInTheDocument());

    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should render loader', async () => {
    const scope = nock(TESTING_HOST).get('/api/v1/tokens/').delay(50).reply(200, { max_reached: false, tokens });

    const { asFragment } = renderUserTokens();

    await screen.findByText('Loading tokens...');

    expect(asFragment()).toMatchSnapshot();

    await waitFor(() => expect(screen.queryByText('Loading tokens...')).not.toBeInTheDocument());

    scope.done();
  });

  it('should sort by state', async () => {
    const scope = nock(TESTING_HOST).get('/api/v1/tokens/').delay(50).reply(200, { max_reached: false, tokens });

    const { asFragment } = renderUserTokens();

    await waitFor(() => expect(screen.queryByText('Loading tokens...')).not.toBeInTheDocument());

    expect(screen.queryByText('sorted ascending')).not.toBeInTheDocument();

    fireEvent.click(screen.queryByText('PERMISSIONS'));

    expect(screen.getByText('sorted ascending')).toBeInTheDocument();
    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should render sorted by state', async () => {
    const scope = nock(TESTING_HOST).get('/api/v1/tokens/').delay(50).reply(200, { max_reached: false, tokens });

    const { asFragment } = renderUserTokens(`${paths.tokens}?sort=-state`);

    await waitFor(() => expect(screen.queryByText('Loading tokens...')).not.toBeInTheDocument());

    expect(screen.getByText('sorted descending')).toBeInTheDocument();
    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should sort by date', async () => {
    const scope = nock(TESTING_HOST).get('/api/v1/tokens/').delay(50).reply(200, { max_reached: false, tokens });

    const { asFragment } = renderUserTokens();

    await waitFor(() => expect(screen.queryByText('Loading tokens...')).not.toBeInTheDocument());

    expect(screen.queryByText('sorted ascending')).not.toBeInTheDocument();

    fireEvent.click(screen.queryByText('LAST SEEN'));

    expect(screen.getByText('sorted ascending')).toBeInTheDocument();
    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should render sorted by date', async () => {
    const scope = nock(TESTING_HOST).get('/api/v1/tokens/').delay(50).reply(200, { max_reached: false, tokens });

    const { asFragment } = renderUserTokens(`${paths.tokens}?sort=-last_seen`);

    await waitFor(() => expect(screen.queryByText('Loading tokens...')).not.toBeInTheDocument());

    expect(screen.getByText('sorted descending')).toBeInTheDocument();
    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should render max tokens reached', async () => {
    const maxTokens = 15;
    const scope = nock(TESTING_HOST)
      .get('/api/v1/tokens/')
      .delay(50)
      .reply(200, { max_reached: true, tokens, max_tokens: maxTokens });

    renderUserTokens();

    await waitFor(() => expect(screen.queryByText('Loading tokens...')).not.toBeInTheDocument());

    expect(screen.getByText(`You have reached a maximum of ${maxTokens} active tokens`)).toBeInTheDocument();

    scope.done();
  });

  it('should render new state added', async () => {
    const scope = nock(TESTING_HOST)
      .get('/api/v1/tokens/')
      .delay(50)
      .reply(200, { max_reached: false, tokens: tokens.map(token => ({ ...token, state: 'new state' })) });

    renderUserTokens();

    await waitFor(() => expect(screen.queryByText('Loading tokens...')).not.toBeInTheDocument());

    expect(screen.queryAllByText(/new state/i)).toHaveLength(5);

    scope.done();
  });

  it('should revoke token successfully', async () => {
    const scope = nock(TESTING_HOST)
      .get('/api/v1/tokens/')
      .delay(50)
      .reply(200, { max_reached: false, tokens })
      .delete(`/api/v1/tokens/${tokens[4].id}/`)
      .delay(50)
      .reply(201, { result: 'ok' })
      .get('/api/v1/tokens/')
      .delay(50)
      .reply(200, { max_reached: false, tokens: tokens.splice(1) });

    renderUserTokens();

    await waitFor(() => expect(screen.queryByText('Loading tokens...')).not.toBeInTheDocument());

    fireEvent.click(screen.queryAllByText(/revoke/i)[0]);

    fireEvent.click(screen.queryByLabelText(/revoke token/i));

    await screen.findByRole('alert');
    await screen.findByText(/token has been revoked/i);

    scope.done();
  });

  it('should fail revoke token and display server validation', async () => {
    const scope = nock(TESTING_HOST)
      .get('/api/v1/tokens/')
      .delay(50)
      .reply(200, { max_reached: false, tokens })
      .delete(`/api/v1/tokens/${tokens[4].id}/`)
      .delay(50)
      .reply(400, { token: ['token is not active'] });

    renderUserTokens();

    await waitFor(() => expect(screen.queryByText('Loading tokens...')).not.toBeInTheDocument());

    fireEvent.click(screen.queryAllByText(/revoke/i)[0]);

    fireEvent.click(screen.queryByLabelText(/revoke token/i));

    await screen.findByRole('alert');
    await screen.findByText(/token is not active/i);

    scope.done();
  });

  it('should fail revoke token and display generic error', async () => {
    const scope = nock(TESTING_HOST)
      .get('/api/v1/tokens/')
      .delay(50)
      .reply(200, { max_reached: false, tokens })
      .delete(`/api/v1/tokens/${tokens[4].id}/`)
      .delay(50)
      .reply(400, { random: [] });

    renderUserTokens();

    await waitFor(() => expect(screen.queryByText('Loading tokens...')).not.toBeInTheDocument());

    fireEvent.click(screen.queryAllByText(/revoke/i)[0]);

    fireEvent.click(screen.queryByLabelText(/revoke token/i));

    await screen.findByRole('alert');
    await screen.findByText(/token revoke failed/i);

    scope.done();
  });

  it('should display token used in last 24h text', async () => {
    const scope = nock(TESTING_HOST).get('/api/v1/tokens/').delay(50).reply(200, { max_reached: false, tokens });

    renderUserTokens();

    await waitFor(() => expect(screen.queryByText('Loading tokens...')).not.toBeInTheDocument());

    fireEvent.click(screen.queryAllByText(/revoke/i)[0]);

    expect(screen.queryByText('You have used this token within the past 24 hours.'));

    scope.done();
  });

  it('should edit the token description successfully', async () => {
    const newDescription = 'Next!!!';
    const scope = nock(TESTING_HOST)
      .get('/api/v1/tokens/')
      .delay(50)
      .reply(200, { max_reached: false, tokens })
      .patch(`/api/v1/tokens/${tokens[4].id}/`, JSON.stringify({ description: newDescription }))
      .delay(50)
      .reply(201, { description: newDescription })
      .get('/api/v1/tokens/')
      .delay(50)
      .reply(200, { max_reached: false, tokens: [{ ...tokens[4], description: newDescription }] });

    renderUserTokens();

    await waitFor(() => expect(screen.queryByText('Loading tokens...')).not.toBeInTheDocument());

    fireEvent.click(screen.queryAllByLabelText(/edit token description/i)[0]);

    expect(screen.queryByLabelText('description')).toHaveValue('no soup for you');

    fireEvent.input(screen.queryByLabelText('description'), {
      target: {
        value: newDescription,
      },
    });

    expect(screen.queryByLabelText('description')).toHaveValue(newDescription);

    fireEvent.click(screen.queryByText(/save/i));

    await screen.findByRole('alert');
    await screen.findByText(/token description has been updated/i);
    await screen.findByText(newDescription);

    scope.done();
  });

  it('should display client validation for description', async () => {
    const scope = nock(TESTING_HOST).get('/api/v1/tokens/').delay(50).reply(200, { max_reached: false, tokens });

    renderUserTokens();

    await waitFor(() => expect(screen.queryByText('Loading tokens...')).not.toBeInTheDocument());

    fireEvent.click(screen.queryAllByLabelText(/edit token description/i)[0]);

    expect(screen.queryByLabelText('description')).toHaveValue('no soup for you');

    fireEvent.input(screen.queryByLabelText('description'), {
      target: {
        value: '',
      },
    });

    expect(screen.getByText('Description is required.')).toBeInTheDocument();

    fireEvent.input(screen.queryByLabelText('description'), {
      target: {
        value: '1',
      },
    });

    expect(screen.getByText('Description must be at least 2 characters.')).toBeInTheDocument();

    fireEvent.input(screen.queryByLabelText('description'), {
      target: {
        value:
          'Lorem ipsum dolor sit amet, consectetur adipisicing elit. Delectus assumenda dolores cupiditate mollitia, obcaecati eaque temporibus cum blanditiis! Natus ratione voluptatum ipsum dolorem illo possimus dolorum nam et illum esse? Lorem ipsum dolor sit amet, consectetur adipisicing elit. Delectus assumenda dolores cupiditate mollitia, obcaecati eaque temporibus cum blanditiis! Natus ratione voluptatum ipsum dolorem illo possimus dolorum nam et illum esse?',
      },
    });

    expect(screen.getByText(`Description can't be more than 250 characters.`)).toBeInTheDocument();

    scope.done();
  });

  it('should fail edit token description and display server validation', async () => {
    const invalidValue = `1'[;*`;
    const scope = nock(TESTING_HOST)
      .get('/api/v1/tokens/')
      .delay(50)
      .reply(200, { max_reached: false, tokens })
      .patch(`/api/v1/tokens/${tokens[4].id}/`, JSON.stringify({ description: invalidValue }))
      .delay(50)
      .reply(400, { errors: { description: [{ message: 'This field is invalid.', code: 'invalid_value' }] } });

    renderUserTokens();

    await waitFor(() => expect(screen.queryByText('Loading tokens...')).not.toBeInTheDocument());

    fireEvent.click(screen.queryAllByLabelText(/edit token description/i)[0]);

    expect(screen.queryByLabelText('description')).toHaveValue('no soup for you');

    fireEvent.input(screen.queryByLabelText('description'), {
      target: {
        value: invalidValue,
      },
    });

    expect(screen.queryByLabelText('description')).toHaveValue(invalidValue);

    fireEvent.click(screen.queryByText(/save/i));

    await screen.findByText('This field is invalid.');

    scope.done();
  });

  it('should fail edit token description and display generic message', async () => {
    const description = 'New Description';
    const scope = nock(TESTING_HOST)
      .get('/api/v1/tokens/')
      .delay(50)
      .reply(200, { max_reached: false, tokens })
      .patch(`/api/v1/tokens/${tokens[4].id}/`, JSON.stringify({ description }))
      .delay(50)
      .reply(400, { errors: { random: [] } });

    renderUserTokens();

    await waitFor(() => expect(screen.queryByText('Loading tokens...')).not.toBeInTheDocument());

    fireEvent.click(screen.queryAllByLabelText(/edit token description/i)[0]);

    expect(screen.queryByLabelText('description')).toHaveValue('no soup for you');
    fireEvent.input(screen.queryByLabelText('description'), {
      target: {
        value: description,
      },
    });

    expect(screen.queryByLabelText('description')).toHaveValue(description);

    fireEvent.click(screen.queryByText('SAVE'));

    await screen.findByRole('alert');
    await screen.findByText('Token description update failed');

    scope.done();
  });

  it('should not render revoke for revoked tokens', async () => {
    const scope = nock(TESTING_HOST)
      .get('/api/v1/tokens/')
      .delay(50)
      .reply(200, { max_reached: false, tokens: [tokens[0]] });

    renderUserTokens();

    await waitFor(() => expect(screen.queryByText('Loading tokens...')).not.toBeInTheDocument());

    expect(screen.queryAllByText('REVOKE')).toHaveLength(0);

    scope.done();
  });

  it('should sort by desc & last_seen by default', async () => {
    const scope = nock(TESTING_HOST).get('/api/v1/tokens/').delay(50).reply(200, { max_reached: false, tokens });

    renderUserTokens();

    await waitFor(() => expect(screen.queryByText('Loading tokens...')).not.toBeInTheDocument());

    expect(screen.getAllByText(/last seen/i)[0].nextSibling).toHaveTextContent('sorted descending');

    scope.done();
  });

  it('should not render top row', async () => {
    const scope = nock(TESTING_HOST).get('/api/v1/tokens/').delay(50).reply(200, { max_reached: false, tokens });

    renderUserTokens();

    await waitFor(() => expect(screen.queryByText('Loading tokens...')).not.toBeInTheDocument());

    expect(screen.queryByText('Data not available')).not.toBeInTheDocument();

    scope.done();
  });

  it('should render custom tooltip on tokenId hover', async () => {
    const scope = nock(TESTING_HOST).get('/api/v1/tokens/').delay(50).reply(200, { max_reached: false, tokens });

    renderUserTokens();

    await waitFor(() => expect(screen.queryByText('Loading tokens...')).not.toBeInTheDocument());

    expect(screen.queryByText(/The token value is only visible when you first create it/)).not.toBeInTheDocument();

    fireEvent.mouseOver(screen.getByText(tokens[0].id));

    await screen.findByText(/The token value is only visible when you first create it/);

    scope.done();
  });
});
