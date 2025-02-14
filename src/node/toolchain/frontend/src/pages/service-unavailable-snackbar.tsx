/*
Copyright 2023 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useServiceUnavailableContext } from 'store/service-unavailable-store';
import Snackbar from '@mui/material/Snackbar';
import CloseIcon from '@mui/icons-material/Close';
import IconButton from '@mui/material/IconButton';
import Button from '@mui/material/Button';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import { styled } from '@mui/material/styles';

import { serviceUnavailable } from 'utils/http';
import { HistoryAndRequestErrorProps } from 'utils/hooks/query';

const CustomSnackbar = styled(Snackbar)(({ theme }) => ({
  [`& .MuiPaper-root`]: {
    backgroundColor: theme.palette.warning.main,
  },
}));

const StyledButton = styled(Button)(() => ({
  color: '#fff',
}));

const ServiceUnavailableSnackbar = () => {
  const client = useQueryClient();

  const { isServiceUnavailable, setIsServiceUnavailable } = useServiceUnavailableContext();

  const retry = () => {
    setIsServiceUnavailable(false);
    client.invalidateQueries({
      predicate: query => {
        const queryCode = (query.state.error as HistoryAndRequestErrorProps)?.retryProps.status;
        const isUnavailable = serviceUnavailable.errorCodes.includes(queryCode);

        return isUnavailable;
      },
    });
  };

  return (
    <CustomSnackbar
      anchorOrigin={{
        vertical: 'bottom',
        horizontal: 'center',
      }}
      open={isServiceUnavailable}
      onClose={() => {
        setIsServiceUnavailable(false);
      }}
      message={
        <Typography variant="body2" color="textPrimary">
          Service unavailable at the moment
        </Typography>
      }
      action={
        <Grid container alignItems="center">
          <Grid item>
            <StyledButton variant="text" onClick={retry}>
              <Typography variant="button1" color="common.white">
                retry
              </Typography>
            </StyledButton>
          </Grid>
          <Grid item>
            <IconButton size="small" aria-label="close" color="inherit" onClick={() => setIsServiceUnavailable(false)}>
              <CloseIcon />
            </IconButton>
          </Grid>
        </Grid>
      }
    />
  );
};

export default ServiceUnavailableSnackbar;
