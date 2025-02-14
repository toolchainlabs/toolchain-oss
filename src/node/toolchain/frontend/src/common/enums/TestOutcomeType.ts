/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

enum TestOutcomeType {
  ERROR = 'error',
  FAILED = 'fail',
  X_FAILED = 'xfail',
  SKIPPED = 'skip',
  X_PASSED = 'xpass',
  X_PASSED_STRICT = 'xpassstrict',
  PASSED = 'pass',
}

export default TestOutcomeType;
