/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import Grid from '@mui/material/Grid';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import { styled } from '@mui/material/styles';

const StyledPaper = styled(Paper)(({ theme }) => ({
  padding: `${theme.spacing(10)} 0px`,
  border: `1px solid transparent`,
  borderRadius: 10,
  backgroundColor: theme.palette.grey[50],
}));

type NoBuildDetailsDataProps = {
  message: string;
};

const NoBuildDetailsData = ({ message }: NoBuildDetailsDataProps) => (
  <StyledPaper elevation={0}>
    <Grid container justifyContent="center">
      <Grid>
        <Typography color="text.disabled" variant="h4">
          {message}
        </Typography>
      </Grid>
    </Grid>
  </StyledPaper>
);

export default NoBuildDetailsData;
