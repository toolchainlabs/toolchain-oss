/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { ReactElement } from 'react';
import { unstable_HistoryRouter as HistoryRouter, Location } from 'react-router-dom';
import { render, RenderOptions } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import { createMemoryHistory } from 'history';
import { QueryParamProvider } from 'use-query-params';
import { ReactRouter6Adapter } from 'use-query-params/adapters/react-router-6';
import queryString from 'query-string';

import { ServiceUnavailableParams, ServiceUnavailableProvider } from 'store/service-unavailable-store';
import { RequestErrorParams, RequestErrorProvider } from 'store/request-error-store';
import { AppVersionProvider, AppVersionStoreInitProps } from 'store/app-version-store';
import { BuildsTableFiltersProvider, RepoBuildsInitParams } from 'store/builds-filters-store';
import { CookiesProvider } from 'react-cookie';
import { UserInitParams, UserProvider } from 'store/user-store';
import { OrgAndRepoInitParams, OrgAndRepoProvider } from 'store/org-repo-store';

import theme from '../src/utils/theme';

type WrapperProps = Partial<Location> & {};
type AllTheProvidersProps = { children: React.ReactElement };
type OptionsProps = Omit<RenderOptions, 'wrapper'> & {
  wrapperProps?: WrapperProps;
  providerProps?: {
    appVersion?: AppVersionStoreInitProps;
    orgAndRepo?: OrgAndRepoInitParams;
    serviceUnavailable?: ServiceUnavailableParams;
    buildsTableFilter?: RepoBuildsInitParams;
    user?: UserInitParams;
    requestError?: RequestErrorParams;
  };
};

const themeComponentOverrides = { MuiButtonBase: { defaultProps: { disableRipple: true } } };

const customRender = (ui: ReactElement, options?: OptionsProps) => {
  const history = createMemoryHistory();
  const hasWrapperProps = !!options?.wrapperProps;

  if (hasWrapperProps) {
    // Set initial route and state if props forwarded
    const { pathname, search, state } = options.wrapperProps;
    const url = !!search ? `${pathname}?${search}` : pathname;
    history.push(url, state);
  }

  const AllTheProviders = ({ children }: AllTheProvidersProps) => (
    <ServiceUnavailableProvider {...options?.providerProps?.serviceUnavailable}>
      <RequestErrorProvider {...options?.providerProps?.requestError}>
        <AppVersionProvider {...options?.providerProps?.appVersion}>
          <ThemeProvider theme={{ ...theme, components: { ...theme.components, ...themeComponentOverrides } }}>
            <BuildsTableFiltersProvider {...options?.providerProps?.buildsTableFilter}>
              <CookiesProvider>
                <UserProvider {...options?.providerProps?.user}>
                  <OrgAndRepoProvider {...options?.providerProps?.orgAndRepo}>{children}</OrgAndRepoProvider>
                </UserProvider>
              </CookiesProvider>
            </BuildsTableFiltersProvider>
          </ThemeProvider>
        </AppVersionProvider>
      </RequestErrorProvider>
    </ServiceUnavailableProvider>
  );

  const renderOptions: RenderOptions = hasWrapperProps
    ? {
        wrapper: ({ children }) => (
          <HistoryRouter history={history as any}>
            <QueryParamProvider
              adapter={ReactRouter6Adapter}
              options={{
                searchStringToObject: queryString.parse,
                objectToSearchString: queryString.stringify,
              }}
            >
              <AllTheProviders>{children}</AllTheProviders>
            </QueryParamProvider>
          </HistoryRouter>
        ),
        ...options,
      }
    : {
        wrapper: ({ children }) => <AllTheProviders>{children}</AllTheProviders>,
        ...options,
      };

  return {
    ...render(ui, renderOptions),
    history,
  };
};

export default customRender;
