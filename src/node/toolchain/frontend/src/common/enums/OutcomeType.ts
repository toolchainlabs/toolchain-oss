/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

enum OutcomeType {
  SUCCESS = 'SUCCESS',
  FAILURE = 'FAILURE',
  ABORTED = 'ABORTED',
  NOT_AVAILABLE = 'NOT_AVAILABLE',
  RUNNING = 'RUNNING',
  SKIPPED = 'SKIPPED',
  MIXED = 'MIXED',
}

export default OutcomeType;
