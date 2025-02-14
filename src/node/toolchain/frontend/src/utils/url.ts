/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import queryString from 'query-string';

/**
 * Generate URL.
 */
const generateUrl = (path: string, baseUrl: string, params: { [key: string]: any } = {}): string => {
  const url = new URL(path, baseUrl);
  url.search = queryString.stringify(params, {
    arrayFormat: 'comma',
  });
  return url.toString();
};

export default generateUrl;
