/*
Copyright 2019 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import 'public-path';

import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryParamProvider } from 'use-query-params';
import { CookiesProvider } from 'react-cookie';
import LinearProgress from '@mui/material/LinearProgress';
import CssBaseline from '@mui/material/CssBaseline';
import { ThemeProvider } from '@mui/material/styles';
import { ReactRouter6Adapter } from 'use-query-params/adapters/react-router-6';
import queryString from 'query-string';

import { OrgAndRepoProvider } from 'store/org-repo-store';
import { UserProvider } from 'store/user-store';
import { BuildsTableFiltersProvider } from 'store/builds-filters-store';
import { RequestErrorProvider } from 'store/request-error-store';
import { ServiceUnavailableProvider } from 'store/service-unavailable-store';
import { AppVersionProvider } from 'store/app-version-store';
import { useAccessToken } from 'utils/hooks/access-token';
import { useInitData } from 'utils/init-data';
import theme from 'utils/theme';
import VersionSnackBar from 'components/new-version-snackbar/new-version-snackbar';
import Routing from 'components/navigation/routing';
import ServiceUnavailableSnackbar from 'pages/service-unavailable-snackbar';

const MainContent = () => {
  useInitData();

  const isLoading = useAccessToken();

  return (
    <>
      <CssBaseline />
      {isLoading ? <LinearProgress /> : <Routing />}
      <ServiceUnavailableSnackbar />
      <VersionSnackBar />
    </>
  );
};

const App = () => (
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <BrowserRouter>
        <RequestErrorProvider>
          <ServiceUnavailableProvider>
            <QueryParamProvider
              adapter={ReactRouter6Adapter}
              options={{
                searchStringToObject: queryString.parse,
                objectToSearchString: queryString.stringify,
              }}
            >
              <BuildsTableFiltersProvider>
                <CookiesProvider>
                  <UserProvider>
                    <OrgAndRepoProvider>
                      <AppVersionProvider>
                        <MainContent />
                      </AppVersionProvider>
                    </OrgAndRepoProvider>
                  </UserProvider>
                </CookiesProvider>
              </BuildsTableFiltersProvider>
            </QueryParamProvider>
          </ServiceUnavailableProvider>
        </RequestErrorProvider>
      </BrowserRouter>
    </ThemeProvider>
  </React.StrictMode>
);

const container = document.getElementById('app');
const root = createRoot(container!);

root.render(<App />);
