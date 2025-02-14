/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

export enum RepoState {
  NOT_PROCESSED = 'not_processed',
  PROCESSING = 'processing',
  SUCCESS = 'success',
  FAILURE = 'failure',
}

export type InputDataType = Array<{
  address: string;
  dependencies?: Array<string>;
  target_type?: string;
}>;

type ResponseType = {
  metadata: Metadata;
  repo: Repo;
  target_list?: InputDataType;
  state?: RepoState;
};

type Metadata = { version: string; pants_version: string };

type Repo = {
  avatar?: string;
  branch: string;
  commit_sha: string;
  full_name: string;
};

export const fetchResults: (
  address: string
) => Promise<ResponseType> = async address => {
  const response = await fetch(address);
  return response.json();
};
