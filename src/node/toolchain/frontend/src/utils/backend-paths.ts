/*
Copyright 2019 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

export default {
  users_ui: {
    LOGIN: '/auth/login/',
    LOGOUT: '/auth/logout/',
  },

  users_api: {
    ME: '/api/v1/users/me/',
    LIST_ORGANIZATIONS: '/api/v1/users/me/customers/',
    LIST_ALL_REPOS: 'api/v1/users/repos/',
    ACCESS_TOKEN: '/api/v1/token/refresh/',
    GET_TOKENS: '/api/v1/tokens/',
    REVOKE_TOKEN: (tokenId: string) => `/api/v1/tokens/${tokenId}/`,
    EMAILS: '/api/v1/users/emails/',
    PATCH_USER: (userApiId: string) => `/api/v1/users/${userApiId}/`,
    ORGANIZATION: (organizationSlug: string) => `/api/v1/customers/${organizationSlug}/`,
    ORGANIZATION_PLAN: (organizationSlug: string) => `/api/v1/customers/${organizationSlug}/plan/`,
    REPO: (organizationSlug: string, repositorySlug: string) =>
      `/api/v1/customers/${organizationSlug}/repos/${repositorySlug}/`,
    WORKER_TOKENS: (organizationSlug: string) => `/api/v1/customers/${organizationSlug}/workers/tokens/`,
    WORKER_TOKEN: (organizationSlug: string, tokenId: string) =>
      `/api/v1/customers/${organizationSlug}/workers/tokens/${tokenId}/`,
  },

  buildsense_api: {
    LIST_BUILDS: (orgId: string, repoId: string) => `/api/v1/repos/${orgId}/${repoId}/builds/`,
    TITLE_SUGGEST: (orgId: string, repoId: string) => `/api/v1/repos/${orgId}/${repoId}/builds/suggest/`,
    RETRIEVE_BUILD: (orgId: string, repoId: string, runId: string) =>
      `/api/v1/repos/${orgId}/${repoId}/builds/${runId}/`,
    RETRIEVE_BUILD_ARTIFACT: (orgId: string, repoId: string, runId: string, artifactId: string) =>
      `/api/v1/repos/${orgId}/${repoId}/builds/${runId}/artifacts/${artifactId}/`,
    RETRIEVE_INDICATORS: (orgId: string, repoId: string) => `api/v1/repos/${orgId}/${repoId}/builds/indicators/`,
  },
};
