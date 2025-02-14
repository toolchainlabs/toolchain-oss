/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { OrgRepoList } from 'common/interfaces/orgs-repo';

const repos: OrgRepoList[] = [
  {
    id: '1',
    slug: 'toolchain',
    name: 'toolchain[dev]',
    customer_slug: 'toolchaindev',
    customer_logo: 'https://jerrypicture.com/logo',
    repo_link: 'https://github.com/toolchaindev/toolchain/',
    scm: 'github',
  },
  {
    id: '2',
    slug: 'second-repo',
    name: 'second repo',
    customer_slug: 'toolchaindev',
    customer_logo: 'https://jerrypicture.com/logo',
    repo_link: 'https://github.com/toolchaindev/second-repo/',
    scm: 'github',
  },
  {
    id: '3',
    slug: 'third-repo',
    name: 'third repo',
    customer_slug: 'toolchaindev',
    customer_logo: 'https://jerrypicture.com/logo',
    repo_link: 'https://bitbucket.org/toolchaindev/third-repo/',
    scm: 'bitbucket',
  },
];

export default repos;
