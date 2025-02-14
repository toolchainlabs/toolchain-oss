/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { Route, Routes } from 'react-router-dom';
import nock from 'nock';

import VersionSnackbar from './new-version-snackbar';
import render from '../../../tests/custom-render';
import OutcomeType from 'common/enums/OutcomeType';
import Artifact from '../../pages/builds/artifact';
import paths from 'utils/paths';
import queryClient from '../../../tests/queryClient';

const TESTING_HOST = 'http://localhost';
const org = 'testorg';
const repo = 'testrepo';
const runId = 'run_id_testing';

jest.mock('utils/init-data', () => ({
  getHost: () => TESTING_HOST,
}));
jest.mock('utils/hooks/access-token');

type RenderParams = {
  appVersion: string;
  versionChecking?: boolean;
};

const renderNewVersionSnackbar = ({ appVersion, versionChecking = true }: RenderParams) =>
  render(
    <>
      <div>Random element</div>
      <VersionSnackbar />
    </>,
    {
      providerProps: {
        appVersion: {
          initAppVersion: appVersion,
          initServerAppVersion: 'version-2',
          initVersionChecking: versionChecking,
        },
      },
    }
  );

describe('<VersionSnackbar />', () => {
  const { reload } = window.location;

  beforeAll(() => {
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { reload: jest.fn() },
    });
  });

  afterAll(() => {
    window.location.reload = reload;
  });

  it('should render the component', () => {
    const { asFragment } = renderNewVersionSnackbar({ appVersion: 'version-1' });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render snackbar', () => {
    renderNewVersionSnackbar({ appVersion: 'version-1' });

    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('should render snackbar text', () => {
    renderNewVersionSnackbar({ appVersion: 'version-1' });

    expect(screen.getByText('A new version of the app is available')).toBeInTheDocument();
  });

  it('should render reload button', () => {
    renderNewVersionSnackbar({ appVersion: 'version-1' });

    expect(screen.getByText('RELOAD')).toBeInTheDocument();
  });

  it('should reload on button click', () => {
    renderNewVersionSnackbar({ appVersion: 'version-1' });

    fireEvent.click(screen.getByText('RELOAD'));

    expect(window.location.reload).toHaveBeenCalled();
  });

  it('should close alert on icon click', async () => {
    renderNewVersionSnackbar({ appVersion: 'version-1' });

    fireEvent.click(screen.getByLabelText('close new version'));

    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
  });

  it('should not close alert on click away', async () => {
    renderNewVersionSnackbar({ appVersion: 'version-1' });

    fireEvent.click(screen.getByText('Random element'));

    await screen.findByRole('alert');
  });

  it('should not show snackbar if no version mismatch', async () => {
    renderNewVersionSnackbar({ appVersion: 'version-2' });

    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('should not show snackbar if version checking explicitly disabled', async () => {
    renderNewVersionSnackbar({ appVersion: 'local', versionChecking: false });

    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});

// Testing Asynchronous Behavior that sets <NewSnackbarVersion />

const OLD_APP_VERSION = 'version1';
const NEW_APP_VERSION = 'version2';

//We need some component that creates a query to test response header no_reload flag in action
const renderTestComponent = ({
  artifactId,
  artifactDescription,
}: Partial<React.ComponentProps<typeof Artifact>> = {}) =>
  render(
    <QueryClientProvider client={queryClient}>
      <Routes>
        <Route
          path="/organizations/:orgSlug/repos/:repoSlug/builds/:runId/"
          element={
            <Artifact artifactId={artifactId} outcome={OutcomeType.SUCCESS} artifactDescription={artifactDescription} />
          }
        />
      </Routes>
      <VersionSnackbar />
    </QueryClientProvider>,
    {
      wrapperProps: {
        pathname: paths.buildDetails(org, repo, runId),
        state: { user_api_id: 'festivus' },
      },
      providerProps: {
        appVersion: {
          initAppVersion: OLD_APP_VERSION,
          initServerAppVersion: OLD_APP_VERSION,
          initVersionChecking: true,
        },
      },
    }
  );

describe('<VersionSnackbar /> Async', () => {
  const artifactId = 'lorem-ipsum';
  const artifactDescription = 'Artifact description';

  const newServerVersion = JSON.stringify({
    version: NEW_APP_VERSION,
  });

  const newServerVersionNoReload = JSON.stringify({
    version: NEW_APP_VERSION,
    no_reload: true,
  });

  beforeEach(() => {
    nock.cleanAll();
    queryClient.clear();
  });

  afterAll(() => {
    nock.cleanAll();
    nock.restore();
    jest.clearAllMocks();
    queryClient.clear();
  });

  it('should render NewVersionSnackbar when new app version is available', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${artifactId}/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, [], {
        'X-SPA-Version': newServerVersion,
      });

    renderTestComponent({ artifactId, artifactDescription });

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByRole('alert');

    scope.done();
  });

  it('should not render NewVersionSnackbar when new app version is available but no_reload flag is set', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${artifactId}/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, [], {
        'X-SPA-Version': newServerVersionNoReload,
      });

    renderTestComponent({ artifactId, artifactDescription });

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());

    scope.done();
  });
});
