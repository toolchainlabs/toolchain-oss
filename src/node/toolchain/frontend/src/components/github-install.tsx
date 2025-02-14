/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import Button from '@mui/material/Button';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import Typography from '@mui/material/Typography';
import { styled } from '@mui/material/styles';
import Grid from '@mui/material/Grid';

import { GithubIconBlack } from 'assets/icons';

const StyledImg = styled('img')(() => ({
  width: 15,
  height: 15,
  filter: 'brightness(0) invert(1)',
  margin: 'auto',
  display: 'block',
}));

const StyledCard = styled(Card)(({ theme }) => ({
  padding: theme.spacing(10),
  maxWidth: 588,
}));

const StyledButton = styled(Button)(({ theme }) => ({
  padding: `${theme.spacing(1)} ${theme.spacing(2)}`,
}));

const GithubInstall = ({ installLink }: { installLink: string }) => (
  <StyledCard elevation={0}>
    <Box textAlign="center">
      <Grid container spacing={5}>
        <Grid item xs={12}>
          <Typography variant="h2">Install the Toolchain GitHub app</Typography>
        </Grid>
        <Grid item xs={12}>
          <Typography variant="h3" color="text.disabled">
            Toolchain needs access to your GitHub account to provide information about your builds
          </Typography>
        </Grid>
        <Grid item xs={12}>
          <StyledButton variant="contained" color="primary" href={installLink}>
            <Grid container spacing={1} alignItems="center">
              <Grid item>
                <StyledImg src={GithubIconBlack} alt="GitHub icon" />
              </Grid>
              <Grid item>
                <Typography variant="button">INSTALL TOOLCHAIN</Typography>
              </Grid>
            </Grid>
          </StyledButton>
        </Grid>
      </Grid>
    </Box>
  </StyledCard>
);

export default GithubInstall;
