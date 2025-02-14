/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { renderHook } from '@testing-library/react-hooks';
import dayjs from 'dayjs';
import { Cookies } from 'react-cookie';
import nock from 'nock';
import { MemoryRouter } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';

import backendPaths from '../backend-paths';
import getAccessToken, { useAccessToken } from './access-token';
import { RequestErrorProvider } from 'store/request-error-store';
import { AppVersionProvider } from 'store/app-version-store';
import { ServiceUnavailableProvider } from 'store/service-unavailable-store';
import queryClient from '../../../tests/queryClient';

const TESTING_HOST = 'http://localhost';

jest.mock('utils/init-data', () => ({
  getHost: () => TESTING_HOST,
}));

const wrapper = ({ children }: any) => (
  <MemoryRouter>
    <QueryClientProvider client={queryClient}>
      <RequestErrorProvider>
        <ServiceUnavailableProvider>
          <AppVersionProvider>{children}</AppVersionProvider>
        </ServiceUnavailableProvider>
      </RequestErrorProvider>
    </QueryClientProvider>
  </MemoryRouter>
);

describe('useAccessToken hook', () => {
  const REFRESH_TOKEN = 'CbhKFtyx3vQLrAKX9jzu';
  const ACCESS_TOKEN_1 = 'tiJn5VVmT6UDwCpMTpOv';
  const ACCESS_TOKEN_2 = 'Ql9wdY9Jthi9cSxX7gen';
  let cookies: Cookies;

  beforeEach(() => {
    cookies = new Cookies();
    nock.cleanAll();
    queryClient.clear();
  });

  afterEach(() => {
    cookies.remove('refreshToken');
  });

  afterAll(() => {
    nock.restore();
    nock.cleanAll();
    queryClient.clear();
    jest.clearAllMocks();
  });

  it('should get access token', async () => {
    cookies.set('refreshToken', REFRESH_TOKEN);
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${REFRESH_TOKEN}`)
      .post(backendPaths.users_api.ACCESS_TOKEN)
      .reply(200, {
        access_token: ACCESS_TOKEN_1,
        expires_at: dayjs().add(10, 'minute').toISOString(),
      });

    const { result, waitForValueToChange } = renderHook(() => useAccessToken(), { wrapper });

    expect(result.current).toEqual(true);

    await waitForValueToChange(() => result.current === false);

    expect(result.current).toEqual(false);
    expect(getAccessToken()).toBe(ACCESS_TOKEN_1);

    const scope1 = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${REFRESH_TOKEN}`)
      .post(backendPaths.users_api.ACCESS_TOKEN)
      .reply(200, {
        access_token: ACCESS_TOKEN_2,
        expires_at: dayjs().add(10, 'minute').toISOString(),
      });

    expect(scope1.isDone()).toBe(false);

    scope.done();
  });

  it('should redirect to login page if no refresh token cookie', async () => {
    // https://github.com/jsdom/jsdom/issues/2112
    delete window.location;
    (window.location as any) = {};

    renderHook(() => useAccessToken(), { wrapper });

    expect(getAccessToken()).toBeNull();
    expect(window.location.href).toBe(`http://localhost${backendPaths.users_ui.LOGIN}`);
    expect(document.cookie).toBe('');
  });

  it('should redirect to login page if refresh token is invalid', async () => {
    // https://github.com/jsdom/jsdom/issues/2112
    delete window.location;
    (window.location as any) = {};
    cookies.set('refreshToken', REFRESH_TOKEN);
    const scope = nock(TESTING_HOST)
      .matchHeader('Authorization', `Bearer ${REFRESH_TOKEN}`)
      .post(backendPaths.users_api.ACCESS_TOKEN)
      .delay(200)
      .reply(403, { message: 'Access denied.' });

    const { waitForNextUpdate } = renderHook(() => useAccessToken(), { wrapper });

    await waitForNextUpdate();

    await waitForNextUpdate();

    expect(getAccessToken()).toBeNull();
    expect(window.location.href).toBe(`http://localhost${backendPaths.users_ui.LOGIN}`);
    expect(document.cookie).toBe('');

    scope.done();
  });
});
