/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { Routes, Route, Navigate, RouteProps, useLocation } from 'react-router-dom';

import UserSettings from 'pages/users/profile';
import ListBuildsPage from 'pages/builds/list';
import BuildDetailsPage from 'pages/builds/build-details';
import OrganizationPage from 'pages/organization/organization';
import NoOrganizationsPage from 'pages/no-organizations/no-organizations';
import RedirectToOrganizationPage from 'components/redirect-to-organization/redirect-to-organizations';
import Layout from 'pages/layout/layout';
import SentryErrorBoundary from 'components/sentry-error-boundary';
import NotFound from 'pages/not-found';
import UserTokens from 'pages/users/tokens';
import WorkerTokens from 'pages/worker-tokens/worker-tokens';

const routes: RouteProps[] = [
  {
    path: '/',
    element: <RedirectToOrganizationPage />,
  },
  {
    path: 'profile',
    element: <UserSettings />,
  },
  {
    path: 'tokens',
    element: <UserTokens />,
  },
  {
    path: 'organizations/:orgSlug/worker-tokens',
    element: <WorkerTokens />,
  },
  {
    path: 'no-organizations',
    element: <NoOrganizationsPage />,
  },
  {
    path: 'organizations/:orgSlug/repos/:repoSlug/builds',
    element: <ListBuildsPage />,
  },
  {
    path: 'organizations/:orgSlug/repos/:repoSlug/builds/:runId/*',
    element: <BuildDetailsPage />,
  },
  {
    path: 'organizations/:orgSlug',
    element: <OrganizationPage />,
  },
];

const Routing = () => {
  const { pathname } = useLocation();

  if (pathname.slice(-1) !== '/') {
    return <Navigate to={`${pathname}/`} />;
  }

  return (
    <Routes>
      {/* Redirect from old details path to new default details path (runId/type/goal) */}
      <Route
        path="organizations/:orgSlug/repos/:repoSlug/builds/:runId/"
        element={<Navigate replace to={`${pathname}type/goal/`} />}
      />
      {routes.map(route => (
        <Route
          key={0}
          path={route.path}
          element={
            <SentryErrorBoundary>
              <Layout>{route.element}</Layout>
            </SentryErrorBoundary>
          }
        />
      ))}
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
};

export default Routing;
