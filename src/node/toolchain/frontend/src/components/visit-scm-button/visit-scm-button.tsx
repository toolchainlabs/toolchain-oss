/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import { styled } from '@mui/material/styles';

import withExternalLink from 'utils/hoc/with-external-link/with-external-link';

interface VisitScmButtonProps {
  url: string;
  scm: string;
}
const StyledButton = styled(Button)(({ theme }) => ({
  borderRadius: theme.spacing(0.5),
  ['& .MuiAvatar-root']: {
    height: 15,
    width: 15,
  },
}));

const VisitScmButton = ({ url, scm }: VisitScmButtonProps) => {
  const ScmButton = ({ Icon }: { Icon?: JSX.Element }) => {
    const buttonText = `VIEW ON ${scm.toUpperCase()}`;

    return (
      <StyledButton variant="outlined" color="primary" startIcon={Icon}>
        <Typography variant="button2" color="primary">
          {buttonText}
        </Typography>
      </StyledButton>
    );
  };

  const Component = withExternalLink(ScmButton, url, scm);

  return scm ? <Component /> : null;
};

export default VisitScmButton;
