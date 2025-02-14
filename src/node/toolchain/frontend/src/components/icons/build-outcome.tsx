/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import CheckCircleOutline from '@mui/icons-material/CheckCircleOutline';
import ErrorOutline from '@mui/icons-material/ErrorOutline';
import Typography from '@mui/material/Typography';
import OutcomeType from 'common/enums/OutcomeType';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import DeleteOutline from '@mui/icons-material/DeleteOutline';
import SkipNext from '@mui/icons-material/SkipNext';
import { styled } from '@mui/material/styles';

type BuildOutcomeProps = {
  outcome: OutcomeType;
  chipVariant?: 'border' | 'noborder';
  chipSize?: 'medium' | 'small';
};

type StyledChipProps = Pick<BuildOutcomeProps, 'chipSize' | 'chipVariant'> & {
  outcome?: OutcomeType;
  isSmallChip: boolean;
  isOutcomeAvailable: boolean;
};

const StyledDeleteIcon = styled(DeleteOutline)(({ theme }) => ({
  color: theme.palette.text.disabled,
}));

const StyledChip = styled(Chip, {
  shouldForwardProp: prop =>
    !(['outcome', 'isSmallChip', 'chipVariant', 'isOutcomeAvailable'] as PropertyKey[]).includes(prop),
})<StyledChipProps>(({ theme, outcome, isSmallChip, chipVariant, isOutcomeAvailable }) => {
  const outcomeBorder: Record<OutcomeType, string> = {
    [OutcomeType.SUCCESS]: theme.palette.success.main,
    [OutcomeType.RUNNING]: theme.palette.warning.main,
    [OutcomeType.FAILURE]: theme.palette.error.main,
    [OutcomeType.ABORTED]: theme.palette.text.disabled,
    [OutcomeType.NOT_AVAILABLE]: theme.palette.text.disabled,
    [OutcomeType.MIXED]: theme.palette.text.disabled,
    [OutcomeType.SKIPPED]: theme.palette.text.disabled,
  };

  const sizeValues = isSmallChip ? { width: 18, height: 18 } : { width: 24, height: 24 };
  const paddingValue = isOutcomeAvailable ? 5 : 12;
  const borderValues =
    chipVariant === 'noborder' ? { border: `1px solid transparent` } : { borderColor: outcomeBorder[outcome] };

  return {
    ...borderValues,
    [`& > svg`]: {
      marginLeft: 5,
      ...sizeValues,
    },
    [`& > .MuiChip-label`]: {
      paddingLeft: paddingValue,
    },
  };
});

export const outcomeTexts: Record<OutcomeType, string> = {
  [OutcomeType.SUCCESS]: 'Success',
  [OutcomeType.RUNNING]: 'Running',
  [OutcomeType.FAILURE]: 'Failed',
  [OutcomeType.ABORTED]: 'Aborted',
  [OutcomeType.NOT_AVAILABLE]: 'Not available',
  [OutcomeType.MIXED]: 'Mixed',
  [OutcomeType.SKIPPED]: 'Skipped',
};

export const OutcomeIcon = ({ outcome }: Pick<BuildOutcomeProps, 'outcome'>) => {
  const outcomeIcons: Record<OutcomeType, React.ReactElement> = {
    [OutcomeType.SKIPPED]: <SkipNext color="warning" titleAccess={OutcomeType.SKIPPED} />,
    [OutcomeType.SUCCESS]: <CheckCircleOutline color="success" titleAccess={OutcomeType.SUCCESS} />,
    [OutcomeType.RUNNING]: <CircularProgress color="warning" size={20} role="circular-progress" />,
    [OutcomeType.FAILURE]: <ErrorOutline color="error" titleAccess={OutcomeType.FAILURE} />,
    [OutcomeType.ABORTED]: <StyledDeleteIcon titleAccess={OutcomeType.ABORTED} />,
    [OutcomeType.NOT_AVAILABLE]: null,
    [OutcomeType.MIXED]: null,
  };

  return outcomeIcons[outcome] || null;
};

export const BuildOutcome = ({ outcome, chipSize = 'medium', chipVariant = 'border' }: BuildOutcomeProps) => {
  const isSmallChip = chipSize === 'small';
  const isOutcomeAvailable = ![OutcomeType.NOT_AVAILABLE, OutcomeType.MIXED].includes(outcome);
  const typographyVariant = isSmallChip ? 'caption' : 'body2';

  return (
    <StyledChip
      label={
        <Typography variant={typographyVariant}>
          {outcomeTexts[outcome] || outcomeTexts[OutcomeType.NOT_AVAILABLE]}
        </Typography>
      }
      variant="outlined"
      avatar={<OutcomeIcon outcome={outcome} />}
      outcome={outcome}
      isSmallChip={isSmallChip}
      chipVariant={chipVariant}
      isOutcomeAvailable={isOutcomeAvailable}
      size={chipSize}
    />
  );
};
