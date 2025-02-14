/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { RouteHandler } from 'cypress/types/net-stubbing';
import mockResponse from '../fixtures/peekdata_fixed.json';

export const DEFAULT_ACCOUNT_NAME = 'defaultAccountName';
export const DEFAULT_REPO_NAME = 'defaultRepoName';

export const defaultUrl = `/app/repo/${DEFAULT_ACCOUNT_NAME}/${DEFAULT_REPO_NAME}/`;

export const processingSuccessResponse = {
  body: {
    target_list: mockResponse,
  },
  statusCode: 200,
};
export const processingFailedResponse = {
  body: {
    state: 'failure',
  },
  statusCode: 200,
};
export const processingInProgressResponse = {
  body: {
    state: 'processing',
  },
  statusCode: 200,
};

export const nockResponse = (
  body: RouteHandler = processingSuccessResponse
) => {
  cy.intercept(
    {
      method: 'GET',
      url: `http://localhost:3000/api/v1/repos/${DEFAULT_ACCOUNT_NAME}/${DEFAULT_REPO_NAME}/`,
    },
    body
  ).as('results');
};

export const nockMailchimp = (email: string) => {
  cy.intercept(
    {
      method: 'GET',
      url: `https://toolchainlabs.us19.list-manage.com/subscribe/post-json?u=4394020cf030b96d17aaabc83&id=908a6f67bb&EMAIL=${email}&c=__jp0`,
    },
    {
      body: `__jp0({ result: 'success', msg: 'Thank you for subscribing!!!' })`,
      statusCode: 200,
    }
  ).as('nockMailchimp');
};
