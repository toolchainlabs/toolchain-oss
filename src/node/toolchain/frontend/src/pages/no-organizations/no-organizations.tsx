/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { styled } from '@mui/material/styles';
import Avatar from '@mui/material/Avatar';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';

import { useUserContext } from 'store/user-store';
import paths from 'utils/paths';

type RouterState = { fromRedirect: boolean };

const StyledPaper = styled(Paper)(({ theme }) => ({
  padding: theme.spacing(10),
  borderRadius: theme.spacing(1),
  backgroundColor: theme.palette.grey[50],
  maxWidth: 588,
}));

const StyledAvatar = styled(Avatar)(({ theme }) => ({
  width: 120,
  height: 120,
  borderRadius: theme.spacing(1),
}));

function NoOrganizationsPage() {
  const location = useLocation();
  const { state } = location as { state: RouterState };
  const navigate = useNavigate();

  useEffect(() => {
    if (!state?.fromRedirect) {
      navigate(paths.home, {
        replace: true,
        state: { fromRedirect: false },
      });
    }
  }, [state, navigate]);

  const { user } = useUserContext();

  return (
    <Grid container spacing={0} direction="column" alignItems="center" justifyContent="center" minHeight="90vh">
      <StyledPaper color="white" elevation={0}>
        <Grid container justifyContent="center" alignItems="center" spacing={5}>
          <Grid item xs={12}>
            <Grid container justifyContent="center" direction="column" alignItems="center" spacing={1}>
              <Grid item>
                <StyledAvatar src={user?.avatar_url} />
              </Grid>
              <Grid item>
                <Typography variant="h1">{user?.username}</Typography>
              </Grid>
            </Grid>
          </Grid>
          <Grid item xs={12}>
            <Typography variant="h3" color="text.disabled" textAlign="center">
              You are not in any organization
            </Typography>
          </Grid>
        </Grid>
      </StyledPaper>
    </Grid>
  );
}

export default NoOrganizationsPage;
