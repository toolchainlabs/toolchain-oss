/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { convertTestOutcomeToTargetOutcome } from './test-outcome-converter';
import OutcomeType from 'common/enums/OutcomeType';
import TestOutcomeType from 'common/enums/TestOutcomeType';

describe('Convert TestOutcome Type to (Target) Outcome Type', () => {
  it('should convert TestOutcome to TargetOutcome', () => {
    const testOutcomes: Array<TestOutcomeType> = [
      TestOutcomeType.ERROR,
      TestOutcomeType.FAILED,
      TestOutcomeType.X_FAILED,
      TestOutcomeType.X_PASSED,
      TestOutcomeType.X_PASSED_STRICT,
      TestOutcomeType.PASSED,
      TestOutcomeType.SKIPPED,
      undefined,
    ];

    const targetOutcomes = [
      OutcomeType.FAILURE,
      OutcomeType.FAILURE,
      OutcomeType.FAILURE,
      OutcomeType.SUCCESS,
      OutcomeType.SUCCESS,
      OutcomeType.SUCCESS,
      OutcomeType.SKIPPED,
      OutcomeType.SUCCESS,
    ];

    testOutcomes.forEach((outcome, index) => {
      expect(convertTestOutcomeToTargetOutcome(outcome)).toBe(targetOutcomes[index]);
    });
  });
});
