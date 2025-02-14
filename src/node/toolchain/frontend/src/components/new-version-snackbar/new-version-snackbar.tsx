/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useEffect, useState } from 'react';
import Snackbar, { SnackbarCloseReason } from '@mui/material/Snackbar';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import CloseIcon from '@mui/icons-material/Close';
import Typography from '@mui/material/Typography';
import Grid from '@mui/material/Grid';
import { styled } from '@mui/material/styles';

import { useAppVersionContext } from 'store/app-version-store';

const StyledSnackbar = styled(Snackbar)(() => ({
  ['& > .MuiPaper-root ']: { backgroundColor: 'rgba(28, 43, 57, 1)' },
}));

const VersionSnackBar = () => {
  const { appVersion, serverAppVersion, versionChecking, noAppReload } = useAppVersionContext();

  const initAppVersionDiffers =
    appVersion && serverAppVersion && versionChecking && appVersion !== serverAppVersion && !noAppReload;
  const [open, setOpen] = useState<boolean>(initAppVersionDiffers);

  const handleClose = (event: Event | React.SyntheticEvent<any>, reason?: SnackbarCloseReason) => {
    if (reason === 'clickaway') {
      return;
    }

    setOpen(false);

    setTimeout(() => {
      if (appVersion && serverAppVersion) {
        setOpen(appVersion !== serverAppVersion && versionChecking && !noAppReload);
      }
    }, 60000 * 30);
  };

  useEffect(() => {
    if (appVersion && serverAppVersion) {
      const isOpen = appVersion !== serverAppVersion && versionChecking && !noAppReload;
      setOpen(isOpen);
    }
  }, [appVersion, serverAppVersion, setOpen, versionChecking, noAppReload]);

  const reloadPage = () => window.location.reload();

  return (
    <StyledSnackbar
      anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      open={open}
      onClose={handleClose}
      message={<Typography variant="body2">A new version of the app is available</Typography>}
      action={
        <Grid container>
          <Grid item>
            <Button variant="text" onClick={reloadPage}>
              <Typography variant="button1" color="primary">
                RELOAD
              </Typography>
            </Button>
          </Grid>
          <Grid item>
            <IconButton size="small" aria-label="close new version" color="inherit" onClick={handleClose}>
              <CloseIcon fontSize="medium" />
            </IconButton>
          </Grid>
        </Grid>
      }
    />
  );
};

export default VersionSnackBar;
