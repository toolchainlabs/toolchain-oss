/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import CustomerStatus from 'common/enums/CustomerStatus';

export interface OrgRepoList {
  id: string;
  slug: string;
  name: string;
  repo_link: string;
  customer_slug: string;
  customer_logo: string;
  scm: string;
}

export interface OrgList {
  id: string;
  slug: string;
  name: string;
  logo_url: string;
  customer_link: string;
  scm: string;
  status?: CustomerStatus;
}

type User = { is_admin: boolean; role: string };

export type Repo = {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
  repo_link: string;
  scm: string;
};

type Metadata = {
  configure_link: string;
  install_link: string;
};

type Customer = {
  id: number;
  slug: string;
  name: string;
  logo_url: string;
  scm: string;
  customer_link: string;
  billing?: string;
};

export type OrganizationPlanAndUsage = {
  plan?: Plan;
  usage: Usage;
};

type Plan = {
  name: string;
  price: string;
  trial_end?: string;
  description: string;
  resources: string[];
};

type Usage = {
  bandwidth: {
    outbound: string;
    inbound: string;
  };
};

export type Organization = {
  customer: Customer;
  metadata: Metadata;
  repos: Repo[];
  user: User;
};
