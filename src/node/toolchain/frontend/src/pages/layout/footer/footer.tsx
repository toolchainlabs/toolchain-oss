/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useEffect } from 'react';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import { captureException } from '@sentry/browser';
import { styled } from '@mui/material/styles';

import AppInitData from 'common/interfaces/appInitData';
import { useAppVersionContext } from 'store/app-version-store';

const StyledButton = styled(Button)(({ theme }) => ({
  backgroundColor: theme.palette.error.main,
  color: theme.palette.common.white,
}));

const Footer = () => {
  const { setAppVersion, setVersionChecking } = useAppVersionContext();
  const appInitDataElement: HTMLElement | null = document.getElementById('app_init_data');
  const appInitDataElementInner: string = appInitDataElement?.innerText;

  const appInitData: AppInitData = appInitDataElementInner && JSON.parse(atob(appInitDataElementInner?.trim()));

  useEffect(() => {
    if (appInitDataElementInner && appInitData && appInitData.assets) {
      setAppVersion(appInitData.assets.version);
      setVersionChecking(!appInitData.assets.disableVersionCheck);
    }
  }, [appInitData, setAppVersion, appInitDataElementInner, setVersionChecking]);

  const throwException = () => captureException(new Error('exception triggered with error_check button'));

  return appInitData && (appInitData.assets || appInitData.flags?.error_check) ? (
    <Grid container justifyContent="flex-end" alignItems="center" spacing={2}>
      {appInitData.flags?.error_check && (
        <Grid item>
          <StyledButton variant="contained" onClick={throwException}>
            TEST SENTRY
          </StyledButton>
        </Grid>
      )}
      {appInitData.assets && (
        <Grid item>
          <Typography variant="caption">{`Version: ${appInitData.assets.version}`}</Typography>
        </Grid>
      )}
    </Grid>
  ) : null;
};

export default Footer;
