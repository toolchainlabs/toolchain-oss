/*
Copyright 2019 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useEffect } from 'react';
import CssBaseline from '@mui/material/CssBaseline';
import Grid from '@mui/material/Grid';
import { styled } from '@mui/material/styles';

import QueryNames from 'common/enums/QueryNames';
import { ToolchainUser } from 'common/interfaces/builds-options';
import { useQueryGet } from 'utils/hooks/query';
import { useUserContext } from 'store/user-store';
import backends from 'utils/backend-paths';

import Footer from './footer/footer';
import Sidebar from './sidebar';

type LayoutProps = {
  children: React.ReactNode;
};

const StyledFooter = styled('footer')(({ theme }) => ({
  padding: theme.spacing(2),
}));

const StyledContainer = styled(Grid)(({ theme }) => ({
  minHeight: '100vh',
  maxWidth: 'calc(100% - 80px)',
  paddingTop: theme.spacing(5),
  paddingLeft: theme.spacing(5),
  paddingRight: theme.spacing(5),
  marginLeft: theme.spacing(10),
  [theme.breakpoints.down('md')]: {
    maxWidth: '100%',
    margin: 'auto',
    paddingTop: theme.spacing(2),
    paddingLeft: theme.spacing(2),
    paddingRight: theme.spacing(2),
  },
}));

const Layout = (props: LayoutProps) => {
  const { children } = props;
  const { setUser } = useUserContext();
  const [{ data: userData }] = useQueryGet<ToolchainUser>([QueryNames.ME], backends.users_api.ME);
  useEffect(() => {
    if (userData) {
      setUser(userData);
    } else {
      setUser(null);
    }
  });

  return (
    <>
      <CssBaseline />
      <Sidebar />
      <StyledContainer container direction="row">
        <Grid item xs={12}>
          <main>{children}</main>
        </Grid>
        <Grid item xs={12} mt="auto">
          <StyledFooter>
            <Footer />
          </StyledFooter>
        </Grid>
      </StyledContainer>
    </>
  );
};

export default Layout;
