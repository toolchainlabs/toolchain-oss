/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { Route, Routes } from 'react-router-dom';
import nock from 'nock';
import MockDate from 'mockdate';

import paths from 'utils/paths';
import WorkerTokens from './worker-tokens';
import sortedWorkerTokens from '../../../tests/__fixtures__/worker-tokens';
import render from '../../../tests/custom-render';
import { dateToDateTimeWithSeparator } from 'utils/datetime-formats';
import queryClient from '../../../tests/queryClient';

const TESTING_HOST = 'http://localhost';
const writeTextMock = jest.fn();

jest.mock('utils/init-data', () => ({
  getHost: () => TESTING_HOST,
}));
jest.mock('utils/hooks/access-token');
// Declare the writeText method since in jsdom its undefined (https://stackoverflow.com/a/62356286/14436058)
Object.assign(navigator, {
  clipboard: {
    writeText: () => {},
  },
});
jest.spyOn(navigator.clipboard, 'writeText').mockImplementation(writeTextMock);

const orgSlug = 'seinfeld';

const renderWorkerToken = (pathname = paths.workerTokens(orgSlug)) =>
  render(
    <QueryClientProvider client={queryClient}>
      <Routes>
        <Route path="/organizations/:orgSlug/worker-tokens/" element={<WorkerTokens />} />
      </Routes>
    </QueryClientProvider>,
    { wrapperProps: { pathname } }
  );

describe('<WorkerTokens />', () => {
  beforeEach(() => {
    nock.cleanAll();
    queryClient.clear();
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
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/workers/tokens/`)
      .delay(50)
      .reply(200, { tokens: [...sortedWorkerTokens] });
    const { asFragment } = renderWorkerToken();

    await waitFor(() => expect(screen.queryByText('Loading worker tokens...')).not.toBeInTheDocument());

    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should render loader', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/workers/tokens/`)
      .delay(50)
      .reply(200, { tokens: [...sortedWorkerTokens] });

    const { asFragment } = renderWorkerToken();

    await screen.findByText('Loading worker tokens...');

    expect(asFragment()).toMatchSnapshot();

    await waitFor(() => expect(screen.queryByText('Loading worker tokens...')).not.toBeInTheDocument());

    scope.done();
  });

  it('should render sort by state on click', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/workers/tokens/`)
      .delay(50)
      .reply(200, { tokens: [...sortedWorkerTokens] });

    const { asFragment } = renderWorkerToken();

    await waitFor(() => expect(screen.queryByText('Loading worker tokens...')).not.toBeInTheDocument());

    expect(screen.queryByText('sorted ascending')).not.toBeInTheDocument();

    fireEvent.click(screen.queryByText('STATE'));

    expect(screen.getByText('sorted ascending')).toBeInTheDocument();
    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should render default sort', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/workers/tokens/`)
      .delay(50)
      .reply(200, { tokens: [...sortedWorkerTokens] });

    const { asFragment } = renderWorkerToken();

    await waitFor(() => expect(screen.queryByText('Loading worker tokens...')).not.toBeInTheDocument());

    expect(screen.getByText('sorted descending')).toBeInTheDocument();
    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should sort by description', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/workers/tokens/`)
      .delay(50)
      .reply(200, { tokens: [...sortedWorkerTokens] });

    const { asFragment } = renderWorkerToken(`${paths.workerTokens(orgSlug)}?sort=description`);

    await waitFor(() => expect(screen.queryByText('Loading worker tokens...')).not.toBeInTheDocument());

    expect(screen.queryByText('sorted descending')).not.toBeInTheDocument();

    fireEvent.click(screen.queryByText('DESCRIPTION'));

    expect(screen.getByText('sorted descending')).toBeInTheDocument();
    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should render sorted by created at', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/workers/tokens/`)
      .delay(50)
      .reply(200, { tokens: [...sortedWorkerTokens] });

    const { asFragment } = renderWorkerToken(`${paths.workerTokens(orgSlug)}?sort=-created_at`);

    await waitFor(() => expect(screen.queryByText('Loading worker tokens...')).not.toBeInTheDocument());

    expect(screen.getByText('sorted descending')).toBeInTheDocument();
    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should blur token on mouse leave', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/workers/tokens/`)
      .delay(50)
      .reply(200, { tokens: [sortedWorkerTokens[0]] });

    renderWorkerToken();

    await waitFor(() => expect(screen.queryByText('Loading worker tokens...')).not.toBeInTheDocument());

    expect(screen.getByTestId('VisibilityIcon')).toBeInTheDocument();
    expect(screen.queryByTestId('VisibilityOffIcon')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('VisibilityIcon'));

    expect(screen.getByTestId('VisibilityOffIcon')).toBeInTheDocument();
    expect(screen.queryByTestId('VisibilityIcon')).not.toBeInTheDocument();

    const tokenContainer = screen.getByTestId('VisibilityOffIcon').parentElement.parentElement.parentElement;

    fireEvent.mouseLeave(tokenContainer);

    expect(screen.getByTestId('VisibilityIcon')).toBeInTheDocument();
    expect(screen.queryByTestId('VisibilityOffIcon')).not.toBeInTheDocument();

    scope.done();
  });

  it('should open and close deactivation dialog on buttons', async () => {
    const token = sortedWorkerTokens[0];
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/workers/tokens/`)
      .delay(50)
      .reply(200, { tokens: [token] });

    renderWorkerToken();

    await waitFor(() => expect(screen.queryByText('Loading worker tokens...')).not.toBeInTheDocument());

    fireEvent.click(screen.getByText(/deactivate/i));

    await screen.findByText(/deactivating token/i);

    expect(screen.getByText(`Description: ${token.description}`)).toBeInTheDocument();
    expect(screen.getByText(`Created at: ${dateToDateTimeWithSeparator(token.created_at)}`)).toBeInTheDocument();

    fireEvent.click(screen.getByText(/keep it/i));

    await waitFor(() => expect(screen.queryByText(/deactivating token/i)).not.toBeInTheDocument());

    expect(screen.queryByText(`Description: ${token.description}`)).not.toBeInTheDocument();
    expect(screen.queryByText(`Created at: ${dateToDateTimeWithSeparator(token.created_at)}`)).not.toBeInTheDocument();

    fireEvent.click(screen.getByText(/deactivate/i));

    await screen.findByText(/deactivating token/i);

    expect(screen.getByText(`Description: ${token.description}`)).toBeInTheDocument();
    expect(screen.getByText(`Created at: ${dateToDateTimeWithSeparator(token.created_at)}`)).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText(/close deactivate/i));

    await waitFor(() => expect(screen.queryByText(/deactivating token/i)).not.toBeInTheDocument());

    expect(screen.queryByText(`Description: ${token.description}`)).not.toBeInTheDocument();
    expect(screen.queryByText(`Created at: ${dateToDateTimeWithSeparator(token.created_at)}`)).not.toBeInTheDocument();

    scope.done();
  });

  it('should succesfully deactivate worker tokens', async () => {
    const token = sortedWorkerTokens[0];
    const tokenAfterDeactivation = { ...token, state: 'inactive' };
    delete tokenAfterDeactivation.token;
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/workers/tokens/`)
      .delay(50)
      .reply(200, { tokens: [token] })
      .delete(`/api/v1/customers/${orgSlug}/workers/tokens/${token.id}/`)
      .delay(50)
      .reply(200, { token: tokenAfterDeactivation })
      .get(`/api/v1/customers/${orgSlug}/workers/tokens/`)
      .delay(50)
      .reply(200, { tokens: [tokenAfterDeactivation] });

    renderWorkerToken();

    await waitFor(() => expect(screen.queryByText('Loading worker tokens...')).not.toBeInTheDocument());

    fireEvent.click(screen.getByText(/deactivate/i));

    await screen.findByText(/deactivating token/i);

    expect(screen.getByText(`Description: ${token.description}`)).toBeInTheDocument();
    expect(screen.getByText(`Created at: ${dateToDateTimeWithSeparator(token.created_at)}`)).toBeInTheDocument();

    fireEvent.click(screen.getAllByText(/deactivate/i)[1]);

    await waitFor(() => expect(screen.queryByText(/deactivating token/i)).not.toBeInTheDocument());

    expect(screen.queryByText(`Description: ${token.description}`)).not.toBeInTheDocument();
    expect(screen.queryByText(`Created at: ${dateToDateTimeWithSeparator(token.created_at)}`)).not.toBeInTheDocument();

    expect(screen.getByText(`Token deactivated`)).toBeInTheDocument();

    scope.done();
  });

  it('should fail worker token deactivation with generic message', async () => {
    const token = sortedWorkerTokens[0];
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/workers/tokens/`)
      .delay(50)
      .reply(200, { tokens: [token] })
      .delete(`/api/v1/customers/${orgSlug}/workers/tokens/${token.id}/`)
      .delay(50)
      .reply(400, { errors: { random: [] } });

    renderWorkerToken();

    await waitFor(() => expect(screen.queryByText('Loading worker tokens...')).not.toBeInTheDocument());

    fireEvent.click(screen.getByText(/deactivate/i));

    await screen.findByText(/deactivating token/i);

    expect(screen.getByText(`Description: ${token.description}`)).toBeInTheDocument();
    expect(screen.getByText(`Created at: ${dateToDateTimeWithSeparator(token.created_at)}`)).toBeInTheDocument();

    fireEvent.click(screen.getAllByText(/deactivate/i)[1]);

    await waitFor(() => expect(screen.queryByText(/deactivating token/i)).not.toBeInTheDocument());

    expect(screen.queryByText(`Description: ${token.description}`)).not.toBeInTheDocument();
    expect(screen.queryByText(`Created at: ${dateToDateTimeWithSeparator(token.created_at)}`)).not.toBeInTheDocument();

    expect(screen.getByText(`Token deactivation failed`)).toBeInTheDocument();

    scope.done();
  });

  it('should fail worker token deactivation with server side message', async () => {
    const token = sortedWorkerTokens[0];
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/workers/tokens/`)
      .delay(50)
      .reply(200, { tokens: [token] })
      .delete(`/api/v1/customers/${orgSlug}/workers/tokens/${token.id}/`)
      .delay(50)
      .reply(400, { errors: { token: ['token is not active'] } });

    renderWorkerToken();

    await waitFor(() => expect(screen.queryByText('Loading worker tokens...')).not.toBeInTheDocument());

    fireEvent.click(screen.getByText(/deactivate/i));

    await screen.findByText(/deactivating token/i);

    expect(screen.getByText(`Description: ${token.description}`)).toBeInTheDocument();
    expect(screen.getByText(`Created at: ${dateToDateTimeWithSeparator(token.created_at)}`)).toBeInTheDocument();

    fireEvent.click(screen.getAllByText(/deactivate/i)[1]);

    await waitFor(() => expect(screen.queryByText(/deactivating token/i)).not.toBeInTheDocument());

    expect(screen.queryByText(`Description: ${token.description}`)).not.toBeInTheDocument();
    expect(screen.queryByText(`Created at: ${dateToDateTimeWithSeparator(token.created_at)}`)).not.toBeInTheDocument();

    expect(screen.getByText(/token is not active/i)).toBeInTheDocument();

    scope.done();
  });

  it('should open and close generate dialog on buttons', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/workers/tokens/`)
      .delay(50)
      .reply(200, { tokens: [] });

    renderWorkerToken();

    await waitFor(() => expect(screen.queryByText('Loading worker tokens...')).not.toBeInTheDocument());

    expect(screen.getByText('No worker tokens found')).toBeInTheDocument();

    fireEvent.click(screen.getByText(/generate new token/i));

    await screen.findByText(/add a description for the new token/i);

    fireEvent.click(screen.getByText(/cancel/i));

    await waitFor(() => expect(screen.queryByText(/add a description for the new token/i)).not.toBeInTheDocument());

    fireEvent.click(screen.getByText(/generate new token/i));

    await screen.findByText(/add a description for the new token/i);

    fireEvent.click(screen.getByLabelText(/close create/i));

    await waitFor(() => expect(screen.queryByText(/add a description for the new token/i)).not.toBeInTheDocument());

    scope.done();
  });

  it('should succesfully generate a new worker token without a custom description', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/workers/tokens/`)
      .delay(50)
      .reply(200, { tokens: [] })
      .post(`/api/v1/customers/${orgSlug}/workers/tokens/`)
      .delay(50)
      .reply(200, { token: sortedWorkerTokens[0] })
      .get(`/api/v1/customers/${orgSlug}/workers/tokens/`)
      .delay(50)
      .reply(200, { tokens: [sortedWorkerTokens[0]] });

    renderWorkerToken();

    await waitFor(() => expect(screen.queryByText('Loading worker tokens...')).not.toBeInTheDocument());

    expect(screen.getByText('No worker tokens found')).toBeInTheDocument();

    fireEvent.click(screen.getByText(/generate new token/i));

    await screen.findByText(/add a description for the new token/i);

    fireEvent.click(screen.getByText('GENERATE'));

    await waitFor(() => expect(screen.queryByText(/add a description for the new token/i)).not.toBeInTheDocument());

    expect(screen.queryByText('No worker tokens found')).not.toBeInTheDocument();

    scope.done();
  });

  it('should succesfully generate a new worker token with a custom description', async () => {
    const description = 'some description';
    const newToken = { ...sortedWorkerTokens[0], description: description };
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/workers/tokens/`)
      .delay(50)
      .reply(200, { tokens: [] })
      .post(`/api/v1/customers/${orgSlug}/workers/tokens/`, JSON.stringify({ description: description }))
      .delay(50)
      .reply(200, { token: newToken })
      .get(`/api/v1/customers/${orgSlug}/workers/tokens/`)
      .delay(50)
      .reply(200, { tokens: [newToken] });

    renderWorkerToken();

    await waitFor(() => expect(screen.queryByText('Loading worker tokens...')).not.toBeInTheDocument());

    expect(screen.getByText('No worker tokens found')).toBeInTheDocument();

    fireEvent.click(screen.getByText(/generate new token/i));

    await screen.findByText(/add a description for the new token/i);

    fireEvent.input(screen.queryByLabelText('description'), {
      target: {
        value: description,
      },
    });

    fireEvent.click(screen.getByText('GENERATE'));

    await waitFor(() => expect(screen.queryByText(/add a description for the new token/i)).not.toBeInTheDocument());

    expect(screen.queryByText('No worker tokens found')).not.toBeInTheDocument();

    expect(screen.getByText(description)).toBeInTheDocument();

    scope.done();
  });

  it('should disable generate button when description is to large', async () => {
    const toLargeDescription =
      'Lorem ipsum dolor sit amet consectetur adipisicing elit. Quibusdam libero id, nobis minus doloribus maiores impedit illum quia maxime voluptatem culpa vero et corporis accusamus laborum ad voluptate? Amet, molestiae? Quibusdam libero id, nobis minus doloribus maiores impedit .';
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/workers/tokens/`)
      .delay(50)
      .reply(200, { tokens: [] });

    renderWorkerToken();

    await waitFor(() => expect(screen.queryByText('Loading worker tokens...')).not.toBeInTheDocument());

    expect(screen.getByText('No worker tokens found')).toBeInTheDocument();

    fireEvent.click(screen.getByText(/generate new token/i));

    await screen.findByText(/add a description for the new token/i);

    fireEvent.input(screen.queryByLabelText('description'), {
      target: {
        value: toLargeDescription,
      },
    });

    expect(screen.getByLabelText('generate token')).toBeDisabled();

    expect(screen.getByText(`Description can't be more than 256 characters.`)).toBeInTheDocument();

    scope.done();
  });

  it('should fail worker token generation with generic message', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/workers/tokens/`)
      .delay(50)
      .reply(200, { tokens: [] })
      .post(`/api/v1/customers/${orgSlug}/workers/tokens/`)
      .delay(50)
      .reply(400, { errors: { random: [{ message: 'This field is invalid.', code: 'invalid_value' }] } });

    renderWorkerToken();

    await waitFor(() => expect(screen.queryByText('Loading worker tokens...')).not.toBeInTheDocument());

    expect(screen.getByText('No worker tokens found')).toBeInTheDocument();

    fireEvent.click(screen.getByText(/generate new token/i));

    await screen.findByText(/add a description for the new token/i);

    fireEvent.click(screen.getByText('GENERATE'));

    await waitFor(() => expect(screen.queryByText(/add a description for the new token/i)).not.toBeInTheDocument());

    await screen.findByText('Token generation failed');

    scope.done();
  });

  it('should fail worker token generation with server side message', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/workers/tokens/`)
      .delay(50)
      .reply(200, { tokens: [] })
      .post(`/api/v1/customers/${orgSlug}/workers/tokens/`)
      .delay(50)
      .reply(400, { errors: { description: [{ message: 'This field is invalid.', code: 'invalid_value' }] } });

    renderWorkerToken();

    await waitFor(() => expect(screen.queryByText('Loading worker tokens...')).not.toBeInTheDocument());

    expect(screen.getByText('No worker tokens found')).toBeInTheDocument();

    fireEvent.click(screen.getByText(/generate new token/i));

    await screen.findByText(/add a description for the new token/i);

    fireEvent.click(screen.getByText('GENERATE'));

    await screen.findByText('This field is invalid.');

    scope.done();
  });

  it('should copy tokenv value to clipboard', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/customers/${orgSlug}/workers/tokens/`)
      .delay(50)
      .reply(200, { tokens: [sortedWorkerTokens[0]] });

    renderWorkerToken();

    await waitFor(() => expect(screen.queryByText('Loading worker tokens...')).not.toBeInTheDocument());

    fireEvent.click(screen.getByTestId('FileCopyIcon'));

    expect(writeTextMock).toHaveBeenCalledWith(sortedWorkerTokens[0].token);

    await screen.findByText('Token value copied');

    scope.done();
  });
});
