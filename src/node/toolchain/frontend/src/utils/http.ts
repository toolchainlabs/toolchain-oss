/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import getAccessToken, { getRefreshToken } from './hooks/access-token';

// DRF returns a JSON message for errors, otherwise fall back to
// a more generic response.
const formatErrorMessage = (error: any): string => error.detail || 'Error handling request.';

const serviceUnavailable = { errorCodes: [502, 503, 499] };

const manualyHandledCodes = { errorCodes: [400] };

const baseConfig: () => RequestInit = () => {
  const accessToken = getAccessToken();
  const refreshToken = getRefreshToken();
  const token = accessToken ? accessToken : refreshToken;

  return {
    credentials: 'omit',
    mode: 'same-origin',
    cache: process.env.NODE_ENV !== 'test' ? 'no-cache' : undefined,
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      Authorization: `Bearer ${token}`,
    },
  };
};

const getSleepTime: () => number = () => 2000;

export { formatErrorMessage, serviceUnavailable, baseConfig, getSleepTime, manualyHandledCodes };
