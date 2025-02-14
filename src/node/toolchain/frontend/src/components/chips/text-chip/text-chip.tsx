/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import { styled } from '@mui/material/styles';

export interface TextChipProps {
  text: string;
}

const StyledChip = styled(Chip)(({ theme }) => ({
  marginRight: 4,
  backgroundColor: theme.palette.grey[300],
}));
const StyledText = styled(Typography)(() => ({
  color: 'inherit',
  fontSize: 12,
}));

const TextChip = ({ text }: TextChipProps) => {
  return <StyledChip size="small" label={<StyledText variant="body2">{text}</StyledText>} />;
};

export default TextChip;
