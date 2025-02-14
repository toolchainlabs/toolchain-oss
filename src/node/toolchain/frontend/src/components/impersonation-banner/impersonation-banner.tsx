/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import Typography from '@mui/material/Typography';
import Grid from '@mui/material/Grid';
import Button from '@mui/material/Button';

import { Impersonation } from 'common/interfaces/appInitData';
import generateUrl from 'utils/url';
import backendPaths from 'utils/backend-paths';
import { getHost } from 'utils/init-data';
import { styled } from '@mui/material/styles';

type ImpersonationBannerProps = { impersonationData: Impersonation };

const StyledGrid = styled(Grid)(({ theme }) => ({
  maxWidth: '100%',
  position: 'sticky',
  top: 0,
  zIndex: '1303 !important' as unknown as 1303,
  backgroundColor: theme.palette.warning.main,
  color: theme.palette.text.primary,
  height: theme.spacing(5),
}));

const StyledButton = styled(Button)(({ theme }) => ({
  backgroundColor: theme.palette.common.white,
  color: theme.palette.warning.main,
  boxShadow: 'none',
}));

const ImpersonationBanner = ({ impersonationData }: ImpersonationBannerProps) => {
  const {
    impersonator_username: impersonatorUsername,
    impersonator_full_name: impersonatorFullName,
    user_username: userUsername,
    user_full_name: userFullName,
  } = impersonationData;
  const impersonator = `${impersonatorUsername}${impersonatorFullName ? ` (${impersonatorFullName})` : ''}`;
  const user = `${userUsername}${userFullName ? ` (${userFullName})` : ''}`;
  const impersonationString = `${impersonator} is ghosting ${user}`;

  const signOut = () => window.location.assign(generateUrl(backendPaths.users_ui.LOGOUT, getHost()));

  return (
    <StyledGrid container justifyContent="center" alignItems="center" spacing={1}>
      <Grid item>
        <Typography variant="subtitle1">{impersonationString}</Typography>
      </Grid>
      <Grid item>
        <StyledButton variant="contained" size="small" onClick={signOut}>
          QUIT GHOSTING MODE
        </StyledButton>
      </Grid>
    </StyledGrid>
  );
};

export default ImpersonationBanner;
