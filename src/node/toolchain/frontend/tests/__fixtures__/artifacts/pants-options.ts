/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { Artifact } from 'common/interfaces/build-artifacts';

export const pantsOptions: Artifact<any> = {
  content_type: 'pants_options',
  name: 'Options',
  content: {
    GLOBAL: {
      backend_packages: ['toolchain.pants', 'toolchain.pants.internal'],
      colors: true,
      local_store_shard_count: 16,
      log_levels_by_target: {},
    },
    auth: {
      auth_file: 'some_file.json',
      org: null,
    },
  },
};

export const pantsOptionsEmpty: Artifact<any> = {
  content_type: 'pants_options',
  name: 'Options',
  content: {},
};
