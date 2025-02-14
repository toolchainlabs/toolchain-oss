/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { renderHook } from '@testing-library/react-hooks';
import nock from 'nock';
import { MemoryRouter } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import dayjs from 'dayjs';
import { captureException } from '@sentry/browser';

import backends from 'utils/backend-paths';
import { UsersOptionsResponse } from 'common/interfaces/builds-options';
import { RequestErrorProvider } from 'store/request-error-store';
import { AppVersionProvider } from 'store/app-version-store';
import { useQueryOptions } from './query';
import users from '../../../tests/__fixtures__/users';
import branches from '../../../tests/__fixtures__/branches';
import goals from '../../../tests/__fixtures__/goals';
import backendPaths from '../backend-paths';
import { ServiceUnavailableProvider } from 'store/service-unavailable-store';
import queryClient from '../../../tests/queryClient';

type WrapperProps = { children: React.ReactElement };

const TESTING_HOST = 'http://localhost';
const MOCK_ACCESS_TOKEN = 'tiJn5VVmT6UDwCpMTpOv';
const REPO_NAME = 'toolchain';
const ORG_NAME = 'nbc';
let timeLeft = 100000;

jest.mock('utils/init-data', () => ({
  getHost: () => TESTING_HOST,
}));
jest.mock('./access-token', () => ({
  __esModule: true,
  // eslint-disable-next-line global-require
  default: jest.fn(() => MOCK_ACCESS_TOKEN),
  // eslint-disable-next-line global-require
  getTokenTimeLeft: jest.fn(() => timeLeft),
  // eslint-disable-next-line global-require
  getRefreshTokenCookieKey: jest.requireActual('./access-token').getRefreshTokenCookieKey,
  // eslint-disable-next-line global-require
  refreshAccessToken: jest.requireActual('./access-token').refreshAccessToken,
  // eslint-disable-next-line global-require
  fetchAccessToken: jest.requireActual('./access-token').fetchAccessToken,
  // eslint-disable-next-line global-require
  getRefreshToken: jest.requireActual('./access-token').getRefreshToken,
}));
jest.mock('utils/http', () => ({
  __esModule: true,
  getSleepTime: () => 50,
  baseConfig: jest.requireActual('utils/http').baseConfig,
  serviceUnavailable: jest.requireActual('utils/http').serviceUnavailable,
  formatErrorMessage: jest.requireActual('utils/http').formatErrorMessage,
  manualyHandledCodes: jest.requireActual('utils/http').manualyHandledCodes,
}));
jest.mock('@sentry/browser');

const wrapper = ({ children }: WrapperProps) => (
  <MemoryRouter>
    <QueryClientProvider client={queryClient}>
      <ServiceUnavailableProvider>
        <RequestErrorProvider>
          <AppVersionProvider>{children}</AppVersionProvider>
        </RequestErrorProvider>
      </ServiceUnavailableProvider>
    </QueryClientProvider>
  </MemoryRouter>
);

describe('useQueryOptions hook', () => {
  afterEach(() => {
    nock.cleanAll();
    queryClient.clear();
    jest.clearAllMocks();
  });
  afterAll(() => jest.clearAllMocks());

  it('useQueryOptions should work with user_api_id', async () => {
    const fieldName = 'user_api_id';
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .options(`/api/v1/repos/${ORG_NAME}/${REPO_NAME}/builds/`)
      .query({ field: fieldName })
      .delay(50)
      .reply(200, { [fieldName]: { values: users } });

    const { result, waitForNextUpdate } = renderHook(
      () =>
        useQueryOptions<UsersOptionsResponse>([fieldName], backends.buildsense_api.LIST_BUILDS(ORG_NAME, REPO_NAME), {
          field: fieldName,
        }),
      { wrapper }
    );

    await waitForNextUpdate();

    expect(result.current[0].data).toEqual({ [fieldName]: { values: users } });
    expect(scope.isDone()).toBe(true);
  });

  it('Should retry 503 status three times and then succeed', async () => {
    const fieldName = 'user_api_id';
    const errorResponse = { message: 'Random error message' };
    const response = { [fieldName]: { values: users } };
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .options(`/api/v1/repos/${ORG_NAME}/${REPO_NAME}/builds/`)
      .times(4)
      .query({ field: fieldName })
      .delay(50)
      .reply(503, errorResponse);

    const scope2 = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .options(`/api/v1/repos/${ORG_NAME}/${REPO_NAME}/builds/`)
      .query({ field: fieldName })
      .delay(50)
      .reply(200, response);

    const { result, waitForNextUpdate } = renderHook(
      () =>
        useQueryOptions<UsersOptionsResponse>([fieldName], backends.buildsense_api.LIST_BUILDS(ORG_NAME, REPO_NAME), {
          field: fieldName,
        }),
      { wrapper }
    );

    await waitForNextUpdate({ timeout: 1000 });

    expect(result.current[0].isLoading).toBe(true);

    await waitForNextUpdate({ timeout: 2000 });

    expect(result.current[0].isLoading).toBe(true);

    await waitForNextUpdate({ timeout: 4000 });

    expect(result.current[0].isLoading).toBe(true);

    await waitForNextUpdate({ timeout: 8000 });

    expect(result.current[0].isLoading).toBe(true);

    await waitForNextUpdate({ timeout: 16000 });

    expect(result.current[0].data).toEqual(response);
    expect(scope.isDone()).toBe(true);
    expect(scope2.isDone()).toBe(true);
  }, 20000);

  it('Should retry 503 status three times and then throw error', async () => {
    const fieldName = 'user_api_id';
    const errorResponse = { message: 'Random error message' };
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .options(`/api/v1/repos/${ORG_NAME}/${REPO_NAME}/builds/`)
      .times(4)
      .query({ field: fieldName })
      .delay(50)
      .reply(503, errorResponse);

    const scope2 = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .options(`/api/v1/repos/${ORG_NAME}/${REPO_NAME}/builds/`)
      .query({ field: fieldName })
      .delay(50)
      .reply(200, errorResponse);

    const { result, waitForNextUpdate } = renderHook(
      () =>
        useQueryOptions<UsersOptionsResponse>([fieldName], backends.buildsense_api.LIST_BUILDS(ORG_NAME, REPO_NAME), {
          field: fieldName,
        }),
      { wrapper }
    );

    await waitForNextUpdate({ timeout: 1000 });

    expect(result.current[0].isLoading).toBe(true);

    await waitForNextUpdate({ timeout: 2000 });

    expect(result.current[0].isLoading).toBe(true);

    await waitForNextUpdate({ timeout: 4000 });

    expect(result.current[0].isLoading).toBe(true);

    await waitForNextUpdate({ timeout: 8000 });

    expect(result.current[0].isLoading).toBe(true);

    await waitForNextUpdate({ timeout: 16000 });

    expect(result.current[0].data).toEqual(errorResponse);
    expect(scope.isDone()).toBe(true);
    expect(scope2.isDone()).toBe(true);
  }, 20000);

  it('Should retry 499 status three times and then throw error', async () => {
    const fieldName = 'user_api_id';
    const errorResponse = { message: 'Random error message' };
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .options(`/api/v1/repos/${ORG_NAME}/${REPO_NAME}/builds/`)
      .times(4)
      .query({ field: fieldName })
      .delay(50)
      .reply(499, errorResponse);

    const scope2 = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .options(`/api/v1/repos/${ORG_NAME}/${REPO_NAME}/builds/`)
      .query({ field: fieldName })
      .delay(50)
      .reply(200, errorResponse);

    const { result, waitForNextUpdate } = renderHook(
      () =>
        useQueryOptions<UsersOptionsResponse>([fieldName], backends.buildsense_api.LIST_BUILDS(ORG_NAME, REPO_NAME), {
          field: fieldName,
        }),
      { wrapper }
    );

    await waitForNextUpdate({ timeout: 1000 });

    expect(result.current[0].isLoading).toBe(true);

    await waitForNextUpdate({ timeout: 2000 });

    expect(result.current[0].isLoading).toBe(true);

    await waitForNextUpdate({ timeout: 4000 });

    expect(result.current[0].isLoading).toBe(true);

    await waitForNextUpdate({ timeout: 8000 });

    expect(result.current[0].isLoading).toBe(true);

    await waitForNextUpdate({ timeout: 16000 });

    expect(result.current[0].data).toEqual(errorResponse);
    expect(scope.isDone()).toBe(true);
    expect(scope2.isDone()).toBe(true);
  }, 20000);

  it('useQueryOptions should work with branch', async () => {
    const fieldName = 'branch';
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .options(`/api/v1/repos/${ORG_NAME}/${REPO_NAME}/builds/`)
      .query({ field: fieldName })
      .delay(50)
      .reply(200, { [fieldName]: { values: branches } });

    const { result, waitForNextUpdate } = renderHook(
      () =>
        useQueryOptions<UsersOptionsResponse>([fieldName], backends.buildsense_api.LIST_BUILDS(ORG_NAME, REPO_NAME), {
          field: fieldName,
        }),
      { wrapper }
    );

    await waitForNextUpdate();

    expect(result.current[0].data).toEqual({ [fieldName]: { values: branches } });
    expect(scope.isDone()).toBe(true);
  });

  it('useQueryOptions should work with goals', async () => {
    const fieldName = 'goals';
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .options(`/api/v1/repos/${ORG_NAME}/${REPO_NAME}/builds/`)
      .query({ field: fieldName })
      .delay(50)
      .reply(200, { [fieldName]: { values: goals } });

    const { result, waitForNextUpdate } = renderHook(
      () =>
        useQueryOptions<UsersOptionsResponse>([fieldName], backends.buildsense_api.LIST_BUILDS(ORG_NAME, REPO_NAME), {
          field: fieldName,
        }),
      { wrapper }
    );

    await waitForNextUpdate();

    expect(result.current[0].data).toEqual({ [fieldName]: { values: goals } });
    expect(scope.isDone()).toBe(true);
  });

  it('should send stringified response to sentry', async () => {
    const fieldName = 'user_api_id';
    const serverUrl = `/api/v1/repos/${ORG_NAME}/${REPO_NAME}/builds/`;
    const response = { error: 'Request failed with 500', requestId: null, requestUrl: serverUrl } as any;
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .options(serverUrl)
      .query({ field: fieldName })
      .delay(50)
      .reply(500, response);

    const { waitForNextUpdate } = renderHook(
      () =>
        useQueryOptions<UsersOptionsResponse>([fieldName], backends.buildsense_api.LIST_BUILDS(ORG_NAME, REPO_NAME), {
          field: fieldName,
        }),
      { wrapper }
    );

    await waitForNextUpdate();

    expect(captureException).toBeCalledWith(Error(JSON.stringify(response)), {
      tags: { requestUrl: serverUrl, requestId: null },
    });
    expect(scope.isDone()).toBe(true);
  });

  it('should send thrown error to sentry', async () => {
    const fieldName = 'user_api_id';
    const serverUrl = `/api/v1/repos/${ORG_NAME}/${REPO_NAME}/builds/`;
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .options(serverUrl)
      .query({ field: fieldName })
      .delay(50)
      .reply(500);

    const { waitForNextUpdate } = renderHook(
      () =>
        useQueryOptions<UsersOptionsResponse>([fieldName], backends.buildsense_api.LIST_BUILDS(ORG_NAME, REPO_NAME), {
          field: fieldName,
        }),
      { wrapper }
    );

    await waitForNextUpdate();

    expect(captureException).toBeCalledWith(Error('SyntaxError: Unexpected end of JSON input'), {
      tags: { requestUrl: serverUrl, requestId: null },
    });
    expect(scope.isDone()).toBe(true);
  });

  it('should refresh token if token expires in less than 40s', async () => {
    timeLeft = -100;
    const fieldName = 'goals1';
    const fieldName2 = 'goals2';
    nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${null}`)
      .post(backendPaths.users_api.ACCESS_TOKEN)
      .reply(200, {
        access_token: MOCK_ACCESS_TOKEN,
        expires_at: dayjs().add(10, 'minute').toISOString(),
      });
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .options(`/api/v1/repos/${ORG_NAME}/${REPO_NAME}/builds/`)
      .query({ field: fieldName })
      .delay(50)
      .reply(200, { [fieldName]: { values: goals } });
    const scope2 = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .options(`/api/v1/repos/${ORG_NAME}/${REPO_NAME}/builds/`)
      .query({ field: fieldName2 })
      .delay(50)
      .reply(200, { [fieldName2]: { values: goals } });

    const { result, waitForNextUpdate } = renderHook(
      () =>
        useQueryOptions<UsersOptionsResponse>([fieldName], backends.buildsense_api.LIST_BUILDS(ORG_NAME, REPO_NAME), {
          field: fieldName,
        }),
      { wrapper }
    );

    const { result: result2, waitForNextUpdate: waitForNextUpdate2 } = renderHook(
      () =>
        useQueryOptions<UsersOptionsResponse>([fieldName2], backends.buildsense_api.LIST_BUILDS(ORG_NAME, REPO_NAME), {
          field: fieldName2,
        }),
      { wrapper }
    );

    await waitForNextUpdate();
    expect(result.current[0].data).toEqual({ [fieldName]: { values: goals } });
    expect(scope.isDone()).toBe(true);

    await waitForNextUpdate2();
    expect(result2.current[0].data).toEqual({ [fieldName2]: { values: goals } });
    expect(scope2.isDone()).toBe(true);
  });

  it('should redirect to login page if refreshing token fails', async () => {
    timeLeft = -100;
    const fieldName = 'goals3';
    delete window.location;
    (window.location as any) = {};
    nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${null}`)
      .post(backendPaths.users_api.ACCESS_TOKEN)
      .reply(403, { message: 'Access denied.' });
    nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${MOCK_ACCESS_TOKEN}`)
      .options(`/api/v1/repos/${ORG_NAME}/${REPO_NAME}/builds/`)
      .query({ field: fieldName })
      .delay(50)
      .reply(200, { [fieldName]: { values: goals } });

    const { waitForNextUpdate } = renderHook(
      () =>
        useQueryOptions<UsersOptionsResponse>([fieldName], backends.buildsense_api.LIST_BUILDS(ORG_NAME, REPO_NAME), {
          field: fieldName,
        }),
      { wrapper }
    );

    await waitForNextUpdate();
    expect(window.location.href).toBe(`${TESTING_HOST}${backendPaths.users_ui.LOGIN}`);
  });
});
