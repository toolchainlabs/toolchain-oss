/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

export enum WorkerTokenState {
  INACTIVE = 'inactive',
  ACTIVE = 'active',
}

export type WorkerToken = {
  id: string;
  created_at: string;
  state: WorkerTokenState;
  description: string;
  token?: string;
};

export type WorkerTokensResponse = { tokens: WorkerToken[] };
