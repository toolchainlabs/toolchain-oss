/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

const MOCK_ACCESS_TOKEN = 'tiJn5VVmT6UDwCpMTpOv';

export default () => MOCK_ACCESS_TOKEN;

const getTokenTimeLeft = () => 100000;
// eslint-disable-next-line global-require
const { getRefreshTokenCookieKey, refreshAccessToken, getRefreshToken } = jest.requireActual('../access-token');

export { getTokenTimeLeft, getRefreshTokenCookieKey, refreshAccessToken, getRefreshToken };
