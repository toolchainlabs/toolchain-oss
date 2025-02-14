/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import withExternalLink from 'utils/hoc/with-external-link/with-external-link';
import { styled } from '@mui/material/styles';

interface ExternalLinkChipProps {
  text: string;
  link: string;
  icon: string;
}

interface ChipComponentProps {
  Icon?: JSX.Element;
  textValue: string;
}

const StyledChip = styled(Chip)(({ theme }) => ({
  marginRight: 4,
  borderColor: theme.palette.primary.main,
  cursor: 'pointer',
}));

const StyledLabel = styled(Typography)(({ theme }) => ({
  color: theme.palette.text.primary,
  fontSize: 12,
}));

const ExternalLinkChip = ({ text, link, icon }: ExternalLinkChipProps) => {
  const ChipComponent = ({ Icon, textValue }: ChipComponentProps) => (
    <StyledChip
      variant="outlined"
      size="small"
      avatar={Icon}
      label={<StyledLabel variant="body2">{textValue}</StyledLabel>}
    />
  );

  const Component = withExternalLink(ChipComponent, link, icon);

  return <Component textValue={text} />;
};

export default ExternalLinkChip;
