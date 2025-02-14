/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { useEffect, useState } from 'react';
import { useCookies } from 'react-cookie';
import { captureException } from '@sentry/browser';

import backendPaths from 'utils/backend-paths';
import { getHost } from 'utils/init-data';
import generateUrl from 'utils/url';
import QueryNames from 'common/enums/QueryNames';
import { useMutationPost } from './query';
import RequestIdHeader from 'utils/constants';

export interface AccessToken {
  access_token: string;
  expires_at: string;
}

const refreshTokenCookieKey: string = 'refreshToken';

let refreshToken: string | null = null;
let accessToken: string | null = null;
let expiresAt: string | null = null;

const fetchAccessToken: () => Promise<any> = async () => {
  const response = await fetch(generateUrl(backendPaths.users_api.ACCESS_TOKEN, getHost()), {
    method: 'POST',
    credentials: 'omit',
    mode: 'same-origin',
    cache: process.env.NODE_ENV !== 'test' ? 'no-cache' : undefined,
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      Authorization: `Bearer ${refreshToken}`,
    },
  });
  return response;
};

const refreshAccessToken: (errorHandler: Function) => void = async (errorHandler = () => {}) => {
  let requestId = null;
  try {
    const response = await fetchAccessToken();
    requestId = response.headers.get(RequestIdHeader);
    const data: AccessToken = await response.json();
    if (!response.ok) {
      throw new Error('Refresh token failed.');
    }
    accessToken = data.access_token;
    expiresAt = data.expires_at;
  } catch (err) {
    captureException(err, {
      tags: { requestUrl: generateUrl(backendPaths.users_api.ACCESS_TOKEN, getHost()), requestId },
    });
    errorHandler();
    window.location.href = generateUrl(backendPaths.users_ui.LOGIN, getHost());
  }
};

// Get time left of access token
const getTokenTimeLeft = () => {
  const tokenExpirationTime = expiresAt ? Date.parse(expiresAt) : 0;
  const timeLeft = tokenExpirationTime - Date.now();

  return timeLeft;
};

// Get current access token
const getAccessToken = () => accessToken;

// Get current refresh token
const getRefreshToken = () => refreshToken;

// Get current refresh token cookie key
const getRefreshTokenCookieKey: () => string = () => refreshTokenCookieKey;

/**
 * Get access token using refresh token if it exists and it is valid.
 * If there is no refresh token cookie or it is invalid, then redirect to
 * the login page.
 */
const useAccessToken = () => {
  const [isLoading, setIsLoading] = useState(true);
  const [cookies, , removeCookie] = useCookies();
  const [{ mutate }] = useMutationPost(
    [QueryNames.POST_REFRESH_TOKEN],
    generateUrl(backendPaths.users_api.ACCESS_TOKEN, getHost()),
    null,
    {
      onError: () => {
        removeCookie(refreshTokenCookieKey);
        window.location.href = generateUrl(backendPaths.users_ui.LOGIN, getHost());
        setIsLoading(false);
      },
      onSuccess: (data: AccessToken) => {
        accessToken = data.access_token;
        expiresAt = data.expires_at;
        setIsLoading(false);
      },
    }
  );

  // This effect is executed only once, this is why
  // the empty array is used as the second argument.
  useEffect(() => {
    const makeRequest = async () => {
      if (cookies[refreshTokenCookieKey]) {
        refreshToken = cookies[refreshTokenCookieKey];
        await mutate({});
      } else {
        removeCookie(refreshTokenCookieKey);
        window.location.href = generateUrl(backendPaths.users_ui.LOGIN, getHost());
      }
    };

    makeRequest();

    return () => {
      refreshToken = null;
      accessToken = null;
      expiresAt = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return isLoading;
};

export {
  useAccessToken,
  getRefreshTokenCookieKey,
  getRefreshToken,
  getTokenTimeLeft,
  refreshAccessToken,
  fetchAccessToken,
};

export default getAccessToken;
