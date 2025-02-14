/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

export interface ToolchainUser {
  api_id: string;
  avatar_url: string;
  email?: string;
  full_name: string;
  username: string;
}

export type Goal = string;

export type PullRequest = number;

export type Branch = string;

export interface UsersOptionsResponse {
  user_api_id?: { values: ToolchainUser[] };
  pr?: { values: PullRequest[] };
  branch?: { values: Branch[] };
  goals?: { values: Goal[] };
}

export interface UsersOptionsResponseNoBuilds {
  status: string;
  docs: string;
}
