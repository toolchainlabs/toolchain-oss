/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

const paths = {
  home: '/',
  profile: '/profile/',
  tokens: '/tokens/',
  noOrganization: '/no-organizations/',
  serviceUnavailable: '/service-unavailable/',
  organization: (org: string) => `/organizations/${org}/`,
  workerTokens: (org: string) => `/organizations/${org}/worker-tokens/`,
  builds: (org: string, repo: string) => `/organizations/${org}/repos/${repo}/builds/`,
  buildDetails: (org: string, repo: string, runId: string) => `/organizations/${org}/repos/${repo}/builds/${runId}/`,
  buildDetailsType: (org: string, repo: string, runId: string, type: string) =>
    `/organizations/${org}/repos/${repo}/builds/${runId}/type/${type}/`,
};

export default paths;
