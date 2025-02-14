/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

type Assets = {
  base_path: string;
  timestamp: string;
  version: string;
  disableVersionCheck?: boolean;
};

type Sentry = {
  dsn: string;
  environment: string;
  release?: string;
};

export type Impersonation = {
  expiry: string;
  impersonator_full_name: string;
  impersonator_username: string;
  user_full_name: string;
  user_username: string;
};

type Flags = {
  error_check: boolean;
};

export default interface AppInitData {
  assets?: Assets;
  impersonation?: Impersonation;
  flags?: Flags;
  host: string;
  sentry: Sentry;
  support_link: string;
}
