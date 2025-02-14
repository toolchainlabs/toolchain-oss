/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import nock from 'nock';
import { Route, Routes } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';

import OutcomeType from 'common/enums/OutcomeType';
import paths from 'utils/paths';
import {
  textLog,
  textPlain,
  textPlainNoContentType,
  textPlainTwo,
  textPlainThree,
  textPlainWrongContentType,
  artifactFromLocalCache,
  artifactFromRemoteCache,
  artifactLocalExecution,
  artifactRemoteExecution,
  artifactOnlyTimings,
  artifactRandomEnvName,
} from '../../../tests/__fixtures__/artifacts/text-and-log';
import { workUnitMetrics, codeCoverage } from '../../../tests/__fixtures__/artifacts/metrics';
import {
  mixedTestResults,
  mixedTestResultsTwo,
  testResultsPassed,
} from '../../../tests/__fixtures__/artifacts/test-results';
import { targets, targetsOnlyOneFolder, targetsEmpty } from '../../../tests/__fixtures__/artifacts/targets';
import { pantsOptions, pantsOptionsEmpty } from '../../../tests/__fixtures__/artifacts/pants-options';
import render from '../../../tests/custom-render';
import Artifact from './artifact';
import ServiceUnavailableSnackbar from 'pages/service-unavailable-snackbar';
import queryClient from '../../../tests/queryClient';

const TESTING_HOST = 'http://localhost';
const org = 'testorg';
const repo = 'testrepo';
const runId = 'run_id_testing';

const allArtifacts = [
  textLog,
  textPlain,
  textPlainNoContentType,
  textPlainTwo,
  textPlainThree,
  textPlainWrongContentType,
  workUnitMetrics,
  codeCoverage,
  targets,
  targetsOnlyOneFolder,
  targetsEmpty,
  pantsOptions,
  pantsOptionsEmpty,
  mixedTestResults,
  mixedTestResultsTwo,
  testResultsPassed,
];

jest.mock('utils/init-data', () => ({
  getHost: () => TESTING_HOST,
}));
jest.mock('utils/hooks/access-token');

const renderArtifact = ({
  artifactId,
  artifactDescription,
  outcome = OutcomeType.SUCCESS,
}: Partial<React.ComponentProps<typeof Artifact>> = {}) =>
  render(
    <QueryClientProvider client={queryClient}>
      <Routes>
        <Route
          path="/organizations/:orgSlug/repos/:repoSlug/builds/:runId/"
          element={<Artifact artifactId={artifactId} outcome={outcome} artifactDescription={artifactDescription} />}
        />
      </Routes>
      <ServiceUnavailableSnackbar />
    </QueryClientProvider>,
    {
      wrapperProps: {
        pathname: paths.buildDetails(org, repo, runId),
        state: { user_api_id: 'festivus' },
      },
    }
  );

const artifactId = 'lorem-ipsum';
const artifactDescription = 'Artifact description';

describe('<Artifact />', () => {
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

  it('should show loader', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${artifactId}/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, [textPlain]);

    const { asFragment } = renderArtifact({ artifactId, artifactDescription });

    await screen.findByRole('progressbar');

    expect(asFragment()).toMatchSnapshot();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    scope.done();
  });

  it('should show data', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${artifactId}/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, allArtifacts);

    const { asFragment } = renderArtifact({ artifactId, artifactDescription });

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should not show data', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${artifactId}/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, [textPlainWrongContentType]);

    renderArtifact({ artifactId, artifactDescription });

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(screen.queryAllByText(/hello world from wrong content type/i)).toHaveLength(0);

    scope.done();
  });

  it('should show error', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${artifactId}/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(403, {
        details: 'Error during API request',
      });

    renderArtifact({ artifactId, artifactDescription });

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(screen.getByRole('alert')).toBeInTheDocument();

    scope.done();
  });

  it('should close error message on click', async () => {
    const user = userEvent.setup();
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${artifactId}/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(403, {
        details: 'Error during API request',
      });

    renderArtifact({ artifactId, artifactDescription });

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByRole('alert');

    user.click(document.body);

    await waitFor(() => expect(screen.queryByRole('alert')).toBeNull());

    scope.done();
  });

  it('should not render artifact with wrong content_type', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${artifactId}/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, [textPlainWrongContentType]);

    renderArtifact({ artifactId, artifactDescription });

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(screen.queryByText(/hello world from wrong content type/i)).toBeNull();

    scope.done();
  });

  it('should not render artifact if artifacts call empty', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${artifactId}/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, []);

    renderArtifact({ artifactId, artifactDescription });

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(screen.queryByText(/hello world from fifth/i)).toBeNull();

    scope.done();
  });

  it('should not render artifact if content_type is null', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${artifactId}/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, [textPlainNoContentType]);

    renderArtifact({ artifactId, artifactDescription });

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(screen.queryByText(/hello world from no content type/i)).toBeNull();

    scope.done();
  });

  it('should render artifact of content type text/log', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${artifactId}/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, [textLog]);

    const { asFragment } = renderArtifact({ artifactId, artifactDescription });

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should render artifact table for work_unit_metrics', async () => {
    const id = 'someId';
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${id}/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, [workUnitMetrics]);

    const { asFragment } = renderArtifact({ artifactId: id, artifactDescription });

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should render artifact for coverage_summary', async () => {
    const id = 'someId';
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${id}/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, [codeCoverage]);

    const { asFragment } = renderArtifact({ artifactId: id, artifactDescription });

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should not render artifact card body (table) for passed test results', async () => {
    const id = 'someId';
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${id}/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, [testResultsPassed]);

    renderArtifact({ artifactId: id, artifactDescription });

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(screen.getByText(/first\/target/i)).toBeInTheDocument();
    expect(screen.queryByText(/test name/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/outcome/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/duration/i)).not.toBeInTheDocument();

    scope.done();
  });

  it('should render artifact card body (table) for mixed test results', async () => {
    const id = 'someId';
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${id}/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, [mixedTestResults]);

    renderArtifact({ artifactId: id, artifactDescription });

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(screen.getByText(/first\/target/i)).toBeInTheDocument();
    expect(screen.getByText(/test name/i)).toBeInTheDocument();
    expect(screen.getByText(/outcome/i)).toBeInTheDocument();
    expect(screen.getByText(/duration/i)).toBeInTheDocument();

    scope.done();
  });

  it('should render success outcome for test results', async () => {
    const id = 'someId';
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${id}/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, [testResultsPassed]);

    renderArtifact({ artifactId: id, artifactDescription });

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(screen.getByText(/first\/target/i)).toBeInTheDocument();
    expect(screen.queryAllByText(/success/i)).toHaveLength(2);

    scope.done();
  });

  it('should render failed outcome for test results', async () => {
    const id = 'someId';
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${id}/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, [mixedTestResults]);

    renderArtifact({ artifactId: id, artifactDescription });

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(screen.getByText(/first\/target/i)).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();

    scope.done();
  });

  it('should show ServiceUnavailableSnackbar and retry request successfully', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${artifactId}/`)
      .times(5)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(503, { error: [{ message: 'Random error message' }] })
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${artifactId}/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, [textPlain]);

    renderArtifact({ artifactId, artifactDescription });

    // eslint-disable-next-line testing-library/prefer-find-by
    await waitFor(() => expect(screen.getByText(/service unavailable at the moment/i)).toBeInTheDocument(), {
      timeout: 20000,
    });

    fireEvent.click(screen.getByText(/retry/i));

    await screen.findByText(/hello world from plain content/i);

    scope.done();
  }, 20000);

  it('should render icons for local cache runs', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${artifactId}/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, [artifactFromLocalCache]);

    renderArtifact({ artifactId, artifactDescription });

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    // From cache icon
    expect(screen.getByTestId('ContentPasteSearchIcon')).toBeInTheDocument();
    // From local env icon
    expect(screen.getByTestId('ComputerIcon')).toBeInTheDocument();
    // Text
    expect(screen.getByLabelText('This result was fetched from the local cache.')).toBeInTheDocument();

    scope.done();
  });

  it('should render icons for remote cache runs', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${artifactId}/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, [artifactFromRemoteCache]);

    renderArtifact({ artifactId, artifactDescription });

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    // From cache icon
    expect(screen.getByTestId('ContentPasteSearchIcon')).toBeInTheDocument();

    // From remote env icon
    expect(screen.getByTestId('FilterDramaIcon')).toBeInTheDocument();
    // Tooltip text
    expect(screen.getByLabelText('This result was fetched from the Toolchain remote cache.')).toBeInTheDocument();

    scope.done();
  });

  it('should render timing and icon for local run', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${artifactId}/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, [artifactLocalExecution]);

    renderArtifact({ artifactId, artifactDescription });

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    const runTimeInSeconds = `${(artifactLocalExecution.timing_msec.run_time / 1000).toFixed(3).slice(0, -1)}s`;

    // Should display runtime duration
    expect(screen.getByText(runTimeInSeconds)).toBeInTheDocument();

    // From remote env icon
    expect(screen.getByTestId('ComputerIcon')).toBeInTheDocument();
    // Tooltip text
    expect(screen.getByLabelText('This ran on a local machine.')).toBeInTheDocument();

    scope.done();
  });

  it('should render timing and icon for remote run', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${artifactId}/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, [artifactRemoteExecution]);

    renderArtifact({ artifactId, artifactDescription });

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    const runTimeInSeconds = `${(artifactRemoteExecution.timing_msec.run_time / 1000).toFixed(3).slice(0, -1)}s`;

    // Should display runtime duration
    expect(screen.getByText(runTimeInSeconds)).toBeInTheDocument();

    // From remote env icon
    expect(screen.getByTestId('FilterDramaIcon')).toBeInTheDocument();
    // Tooltip text
    expect(screen.getByLabelText('This ran on a remote worker.')).toBeInTheDocument();

    scope.done();
  });

  it('should render only timings if env_name is not present', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${artifactId}/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, [artifactOnlyTimings]);

    renderArtifact({ artifactId, artifactDescription });

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    const runTimeInSeconds = `${(artifactOnlyTimings.timing_msec.run_time / 1000).toFixed(3).slice(0, -1)}s`;

    // Should display runtime duration
    expect(screen.getByText(runTimeInSeconds)).toBeInTheDocument();

    // No icons
    expect(screen.queryByTestId('FilterDramaIcon')).not.toBeInTheDocument();
    expect(screen.queryByTestId('ComputerIcon')).not.toBeInTheDocument();
    expect(screen.queryByTestId('ContentPasteSearchIcon')).not.toBeInTheDocument();
    // No tooltip text
    expect(screen.queryByLabelText('This ran on a remote worker.')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('This ran on a local machine.')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('This result was fetched from the Toolchain remote cache.')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('This result was fetched from the local cache.')).not.toBeInTheDocument();

    scope.done();
  });

  it('should render only timings env name test if env_name is random', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/testorg/testrepo/builds/run_id_testing/artifacts/${artifactId}/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, [artifactRandomEnvName]);

    renderArtifact({ artifactId, artifactDescription });

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    const runTimeInSeconds = `${(artifactRandomEnvName.timing_msec.run_time / 1000).toFixed(3).slice(0, -1)}s`;

    // Should display runtime duration
    expect(screen.getByText(runTimeInSeconds)).toBeInTheDocument();
    // Should display random env name text
    expect(screen.getByText(`| ${artifactRandomEnvName.env_name}`)).toBeInTheDocument();

    // No icons
    expect(screen.queryByTestId('FilterDramaIcon')).not.toBeInTheDocument();
    expect(screen.queryByTestId('ComputerIcon')).not.toBeInTheDocument();
    expect(screen.queryByTestId('ContentPasteSearchIcon')).not.toBeInTheDocument();
    // No tooltip text
    expect(screen.queryByLabelText('This ran on a remote worker.')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('This ran on a local machine.')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('This result was fetched from the Toolchain remote cache.')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('This result was fetched from the local cache.')).not.toBeInTheDocument();

    scope.done();
  });
});
