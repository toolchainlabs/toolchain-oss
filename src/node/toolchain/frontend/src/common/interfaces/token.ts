/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

type Customer = {
  id: string;
  name: string;
  slug: string;
};

type Repo = {
  id: string;
  name: string;
  slug: string;
};

export enum TokenState {
  ACTIVE = 'Active',
  REVOKED = 'Revoked',
  EXPIRED = 'Expired',
}

export type Token = {
  can_revoke: boolean;
  customer: Customer;
  description: string;
  expires_at: string;
  id: string;
  issued_at: string;
  last_seen: string;
  permissions: string[];
  repo: Repo;
  state: TokenState;
};

export type GetTokensResponse = {
  max_reached: boolean;
  max_tokens: number;
  tokens: Token[];
};
