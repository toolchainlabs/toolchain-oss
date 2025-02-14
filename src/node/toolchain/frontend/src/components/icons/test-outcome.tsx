/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';
import DoneAll from '@mui/icons-material/DoneAll';
import ErrorOutline from '@mui/icons-material/ErrorOutline';
import Cancel from '@mui/icons-material/Cancel';
import Check from '@mui/icons-material/Check';
import RadioButtonUnchecked from '@mui/icons-material/RadioButtonUnchecked';
import SkipNext from '@mui/icons-material/SkipNext';

import TestOutcomeType from 'common/enums/TestOutcomeType';
import { styled } from '@mui/material/styles';

type TestOutcomeProps = {
  outcome: TestOutcomeType;
  variant?: 'filled' | 'outlined';
  size?: 'small' | 'medium';
};

const SyledChip = styled(Chip)(({ theme }) => ({
  border: 0,
  [`& > .MuiChip-label`]: {
    paddingLeft: `0 ${theme.spacing(1)}`,
  },
}));

export const testOutcomeText: Record<TestOutcomeType, string> = {
  [TestOutcomeType.PASSED]: 'Passed',
  [TestOutcomeType.FAILED]: 'Failed',
  [TestOutcomeType.ERROR]: 'Error',
  [TestOutcomeType.X_PASSED_STRICT]: 'Xpassed (strict)',
  [TestOutcomeType.X_PASSED]: 'Xpassed',
  [TestOutcomeType.X_FAILED]: 'Xfailed',
  [TestOutcomeType.SKIPPED]: 'Skipped',
};

export const TestOutcomeIcon = ({ outcome }: { outcome: TestOutcomeType }) => {
  const outcomeIcons: Record<TestOutcomeType, React.ReactElement> = {
    [TestOutcomeType.PASSED]: <DoneAll className={outcome} color="success" />,
    [TestOutcomeType.FAILED]: <ErrorOutline className={outcome} color="error" />,
    [TestOutcomeType.ERROR]: <Cancel className={outcome} color="error" />,
    [TestOutcomeType.X_PASSED_STRICT]: <Check className={outcome} color="error" />,
    [TestOutcomeType.X_PASSED]: <Check className={outcome} color="warning" />,
    [TestOutcomeType.X_FAILED]: <RadioButtonUnchecked className={outcome} color="warning" />,
    [TestOutcomeType.SKIPPED]: <SkipNext className={outcome} color="warning" />,
  };

  return outcomeIcons[outcome];
};

const TestOutcome = ({ outcome, variant = 'outlined', size = 'small' }: TestOutcomeProps) => {
  const isValidOutcomeType = Object.values(TestOutcomeType).includes(outcome);

  return isValidOutcomeType ? (
    <SyledChip
      label={<Typography variant="body2">{testOutcomeText[outcome]}</Typography>}
      variant={variant}
      avatar={<TestOutcomeIcon outcome={outcome} />}
      size={size}
    />
  ) : null;
};

export default TestOutcome;
