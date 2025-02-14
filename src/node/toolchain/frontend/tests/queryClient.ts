/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { QueryClient } from '@tanstack/react-query';

const queryClient = new QueryClient({
  logger: {
    log: (...args) => {
      return args;
    },
    warn: (...args) => {
      return args;
    },
    error: () => {},
  },
});

export default queryClient;
