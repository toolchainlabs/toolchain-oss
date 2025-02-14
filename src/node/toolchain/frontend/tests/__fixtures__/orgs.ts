/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { Organization, OrganizationPlanAndUsage, OrgList } from 'common/interfaces/orgs-repo';
import CustomerStatus from 'common/enums/CustomerStatus';

const organizations: OrgList[] = [
  {
    id: '1',
    slug: 'toolchaindev',
    name: 'toolchaindev',
    logo_url: 'https://kramer.com/logo',
    customer_link: 'https://github.com/toolchaindev/',
    scm: 'github',
    status: CustomerStatus.FREE_TRIAL,
  },
  {
    id: '2',
    slug: 'Steinbrenner',
    name: 'Steinbrenner',
    logo_url: 'https://kramer.com/logo',
    customer_link: 'https://github.com/Steinbrenner/',
    scm: 'github',
  },
  {
    id: '3',
    slug: 'third-organization',
    name: 'third organization',
    logo_url: 'https://kramer.com/logo',
    customer_link: 'https://bitbucket.org/third-organization/',
    scm: 'bitbucket',
    status: CustomerStatus.LIMITED,
  },
];

export const organization: Organization = {
  customer: {
    id: 1,
    slug: 'toolchaindev',
    name: 'toolchaindev',
    logo_url: 'https://jerrypicture.com/logo',
    scm: 'github',
    customer_link: 'https://github.com/toolchaindev/',
  },
  metadata: {
    configure_link: null,
    install_link: null,
  },
  repos: [
    {
      id: 1,
      slug: 'toolchain',
      name: 'toolchain[dev]',
      is_active: true,
      repo_link: 'https://github.com/toolchaindev/toolchain/',
      scm: 'github',
    },
    {
      id: 2,
      slug: 'second-repo',
      name: 'second repo',
      is_active: true,
      repo_link: 'https://github.com/toolchaindev/second-repo/',
      scm: 'github',
    },
    {
      id: 3,
      slug: 'third-repo',
      name: 'third repo',
      is_active: true,
      repo_link: 'https://bitbucket.org/toolchaindev/third-repo/',
      scm: 'bitbucket',
    },
  ],
  user: { role: 'user', is_admin: false },
};

export const organizationPlanStarter: OrganizationPlanAndUsage = {
  plan: {
    name: 'Starter',
    price: '499$/month',
    description: 'Some lengthy starter description',
    resources: ['Resource one', 'Resource two'],
    trial_end: '2022-08-31',
  },
  usage: {
    bandwidth: {
      inbound: '111.0 MB',
      outbound: '322.0 MB',
    },
  },
};

export const organizationPlanEnterprise: OrganizationPlanAndUsage = {
  plan: {
    name: 'Enterprise',
    price: '499$/month',
    description: 'Some lengthy enterprise description',
    resources: ['Resource one', 'Resource two', 'Resource three'],
  },
  usage: {
    bandwidth: {
      inbound: '222.0 MB',
      outbound: '444.0 MB',
    },
  },
};

export const organizationPlanEmpty: OrganizationPlanAndUsage = {
  plan: null,
  usage: {
    bandwidth: {
      inbound: null,
      outbound: null,
    },
  },
};

export default organizations;
