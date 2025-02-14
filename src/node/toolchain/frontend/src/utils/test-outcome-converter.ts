/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import OutcomeType from 'common/enums/OutcomeType';
import TestOutcomeType from 'common/enums/TestOutcomeType';

export const convertTestOutcomeToTargetOutcome = (testOutcome: TestOutcomeType) => {
  switch (testOutcome) {
    case TestOutcomeType.ERROR:
    case TestOutcomeType.FAILED:
    case TestOutcomeType.X_FAILED:
      return OutcomeType.FAILURE;
    case TestOutcomeType.X_PASSED:
    case TestOutcomeType.PASSED:
    case TestOutcomeType.X_PASSED_STRICT:
    case TestOutcomeType.X_PASSED:
      return OutcomeType.SUCCESS;
    case TestOutcomeType.SKIPPED:
      return OutcomeType.SKIPPED;
    default:
      return OutcomeType.SUCCESS;
  }
};
