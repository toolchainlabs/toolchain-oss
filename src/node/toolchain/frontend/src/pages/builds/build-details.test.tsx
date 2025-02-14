/*
Copyright 2019 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { screen, fireEvent, waitFor, act } from '@testing-library/react';
import MockDate from 'mockdate';
import nock from 'nock';
import { QueryClientProvider } from '@tanstack/react-query';
import userEvent from '@testing-library/user-event';

import { BuildResponse, BuildsListResponse } from 'common/interfaces/builds';
import paths from 'utils/paths';
import buildsList from '../../../tests/__fixtures__/builds-list';

import {
  textPlain,
  textPlainTwo,
  textPlainThree,
  textPlainFour,
} from '../../../tests/__fixtures__/artifacts/text-and-log';
import users from '../../../tests/__fixtures__/users';
import branches from '../../../tests/__fixtures__/branches';
import goals from '../../../tests/__fixtures__/goals';
import render from '../../../tests/custom-render';
import BuildDetailsPage from './build-details';
import ListBuildsPage from './list';
import { durationToFormat } from 'utils/datetime-formats';
import { codeCoverage, workUnitMetrics } from '../../../tests/__fixtures__/artifacts/metrics';
import { testResultsV2 } from '../../../tests/__fixtures__/artifacts/test-results';
import { pantsOptions } from '../../../tests/__fixtures__/artifacts/pants-options';
import { targets } from '../../../tests/__fixtures__/artifacts/targets';
import repos from '../../../tests/__fixtures__/repos';
import orgs from '../../../tests/__fixtures__/orgs';
import { workunits, traceData } from '../../../tests/__fixtures__/download-file';
import downloadFile from 'utils/download-file';
import queryClient from '../../../tests/queryClient';

const buildsMock: BuildResponse[] = buildsList.map(build => ({
  run_info: build,
}));
const TESTING_HOST = 'http://localhost';
const orgSlug = 'toolchaindev';
const repoSlug = 'toolchain';
const runId = 'run_id_testing';
const type = 'goal';
const path = paths.buildDetailsType(orgSlug, repoSlug, runId, type);

jest.mock('utils/init-data', () => ({
  getHost: () => TESTING_HOST,
}));
jest.mock('utils/datetime-formats', () => ({
  ...Object.assign(jest.requireActual('utils/datetime-formats')),
  dateTimeToLocal: (value: any) => value,
}));
jest.mock('utils/hooks/access-token');
jest.mock('utils/download-file', () => ({
  __esModule: true,
  default: jest.fn(),
}));

const renderRetrieveBuild = (initRoute = path, initParams?: any, initSearch?: string) =>
  render(
    <QueryClientProvider client={queryClient}>
      <Routes>
        <Route path="/organizations/:orgSlug/repos/:repoSlug/builds/:runId/*" element={<BuildDetailsPage />} />
        <Route path="/organizations/:orgSlug/repos/:repoSlug/builds/" element={<ListBuildsPage />} />
      </Routes>
    </QueryClientProvider>,
    {
      wrapperProps: { pathname: initRoute, search: initSearch, state: { user_api_id: 'festivus' } },
      providerProps: { buildsTableFilter: { initParams } },
    }
  );

describe('BuildDetailsPage', () => {
  beforeEach(() => {
    queryClient.clear();
    nock.cleanAll();
    MockDate.set(new Date('2019-05-14T11:01:58.135Z'));
  });

  afterEach(() => {
    MockDate.reset();
  });

  afterAll(() => {
    nock.cleanAll();
    nock.restore();
    jest.clearAllMocks();
    queryClient.clear();
  });

  it('should render component', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, buildsMock[0])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree]);

    const { asFragment } = renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should show loader', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, buildsMock[0])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree]);

    const { asFragment } = renderRetrieveBuild();

    await screen.findByRole('progressbar');

    expect(asFragment()).toMatchSnapshot();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    scope.done();
  });

  it('should show error', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(403, {
        details: 'Error during API request',
      })
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null });

    const { asFragment } = renderRetrieveBuild();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    await screen.findByRole('alert');

    expect(asFragment()).toMatchSnapshot();

    scope.done();
  });

  it('should close error message on click', async () => {
    const user = userEvent.setup();
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(403, {
        details: 'Error during API request',
      })
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null });

    renderRetrieveBuild();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    const errorModal = await screen.findByRole('alert');

    expect(errorModal).toBeInTheDocument();

    user.click(document.body);

    await waitFor(() => {
      expect(screen.queryByRole('alert')).toBeNull();
    });

    scope.done();
  });

  it('should render tabs for outputs, details and targets', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, buildsMock[0])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree]);

    renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    expect(screen.getByText('Outputs')).toBeInTheDocument();
    expect(screen.getByText('Details')).toBeInTheDocument();
    expect(screen.getByText('Targets')).toBeInTheDocument();

    scope.done();
  });

  it('should render subtabs for outputs', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, buildsMock[0])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree]);

    renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    expect(screen.getByText('lint')).toBeInTheDocument();
    expect(screen.getByText('typecheck')).toBeInTheDocument();

    scope.done();
  });

  it('should render tabs with artifact type as tab title', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, buildsMock[0])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree]);

    renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    const artifactKeys = Object.keys(buildsMock[0].run_info.build_artifacts);
    const artifactSet = new Set(
      artifactKeys.map(
        key =>
          `${buildsMock[0].run_info.build_artifacts[key].type
            .charAt(0)
            .toUpperCase()}${buildsMock[0].run_info.build_artifacts[key].type.slice(1)}s`
      )
    );

    const tabKeys = [...artifactSet];

    tabKeys.forEach(key => screen.queryAllByText(key).forEach(element => expect(element).toBeInTheDocument()));

    scope.done();
  });

  it('should render 3 cards for LINT', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[0])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree]);

    renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    scope.done();
  });

  it('should change between tabs and display TYPECHECK', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, buildsMock[0])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-4.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainFour]);

    renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    fireEvent.click(screen.queryByText('typecheck'));
    fireEvent.click(screen.queryByText('typecheck'));

    await screen.findByText(/first typecheck/i);

    scope.done();
  });

  it('should render 1 card for TYPECHECK', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .query({ user_api_id: 'festivus' })
      .delay(100)
      .reply(200, buildsMock[0])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-4.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainFour]);

    renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    fireEvent.click(screen.queryByText('typecheck'));

    await screen.findByText(/first typecheck/i);

    expect(screen.queryByText(/second typecheck/)).not.toBeInTheDocument();

    scope.done();
  });

  it('should refresh data on REFRESH button', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .twice()
      .delay(100)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[5])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null });

    renderRetrieveBuild();

    await screen.findByText('Command');

    fireEvent.click(screen.queryByText(/REFRESH/));

    await screen.findByRole('progressbar');

    await screen.findByText('Command');

    scope.done();
  });

  it('should not render data', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .delay(100)
      .query({ user_api_id: 'festivus' })
      .reply(200, null)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null });

    renderRetrieveBuild();

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    expect(screen.queryByText(/Command/)).not.toBeInTheDocument();

    scope.done();
  });

  it('should render options data', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .delay(100)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[10])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/aggregated_workunit_metrics.json/`)
      .delay(50)
      .reply(200, [workUnitMetrics])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/pants_options.json/`)
      .delay(50)
      .reply(200, [pantsOptions]);

    renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    fireEvent.click(screen.queryByTitle('Details'));

    await screen.findByText(/some metric two/i);
    await screen.findByText(/some metric three/i);
    await screen.findByText(/some metric four/i);

    fireEvent.click(screen.queryByTitle('pants_options'));

    await screen.findByText(/global/i);
    await screen.findByText(/colors/i);

    scope.done();
  });

  it('should render metrics data', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[0])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/aggregated_workunit_metrics.json/`)
      .delay(50)
      .reply(200, [workUnitMetrics]);

    renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    fireEvent.click(screen.queryByTitle('Details'));

    await screen.findByText(/some metric two/i);
    await screen.findByText(/some metric three/i);
    await screen.findByText(/some metric four/i);

    scope.done();
  });

  it('should cache options data call', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[10])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/aggregated_workunit_metrics.json/`)
      .delay(50)
      .reply(200, [workUnitMetrics])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/pants_options.json/`)
      .delay(50)
      .reply(200, [pantsOptions]);

    renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    fireEvent.click(screen.queryByTitle('Details'));

    await screen.findByText(/some metric two/i);
    await screen.findByText(/some metric three/i);
    await screen.findByText(/some metric four/i);

    fireEvent.click(screen.queryByTitle('pants_options'));

    // A progressbar is present on first click
    expect(screen.getByRole('progressbar')).toBeInTheDocument();

    await screen.findByText(/global/i);
    await screen.findByText(/colors/i);

    fireEvent.click(screen.queryByTitle('Outputs'));

    expect(screen.getByText(/first lint/i)).toBeInTheDocument();
    expect(screen.getByText(/second lint/i)).toBeInTheDocument();
    expect(screen.getByText(/third lint/i)).toBeInTheDocument();

    fireEvent.click(screen.queryByTitle('Details'));

    expect(screen.getByText(/some metric two/i)).toBeInTheDocument();
    expect(screen.getByText(/some metric three/i)).toBeInTheDocument();
    expect(screen.getByText(/some metric four/i)).toBeInTheDocument();

    fireEvent.click(screen.queryByTitle('pants_options'));

    // A progressbar is not present on second click
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();

    expect(screen.getByText(/global/i)).toBeInTheDocument();
    expect(screen.getByText(/colors/i)).toBeInTheDocument();

    scope.done();
  });

  it('should cache artifact data call', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[0])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/aggregated_workunit_metrics.json/`)
      .delay(50)
      .reply(200, [workUnitMetrics]);

    renderRetrieveBuild();

    await screen.findByText('Command');

    // Progressbars are present (multiple due to multiple lint artifacts)
    expect(screen.queryAllByRole('progressbar')).toHaveLength(3);

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    fireEvent.click(screen.queryByTitle('Details'));

    await screen.findByText(/some metric two/i);
    await screen.findByText(/some metric three/i);
    await screen.findByText(/some metric four/i);

    fireEvent.click(screen.queryByTitle('Outputs'));

    // No progressbars (multiple due to multiple lint artifacts) are present on second click
    expect(screen.queryAllByRole('progressbar')).toHaveLength(0);
    expect(screen.getByText(/first lint/i)).toBeInTheDocument();
    expect(screen.getByText(/second lint/i)).toBeInTheDocument();
    expect(screen.getByText(/third lint/i)).toBeInTheDocument();

    scope.done();
  });

  it('should display no details message under Details (no run artifacts response)', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[7])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null });

    renderRetrieveBuild(paths.buildDetailsType(orgSlug, repoSlug, runId, 'run'));

    await screen.findByText('Command');

    expect(screen.getByText(/there are no details in this build/i)).toBeInTheDocument();

    scope.done();
  });

  it('should display no outputs message under Outputs (no goal artifacts response)', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[7])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null });

    renderRetrieveBuild();

    await screen.findByText('Command');

    expect(screen.getByText(/there are no outputs in this build/i)).toBeInTheDocument();

    scope.done();
  });

  it('should render pytest outputs', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[8])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/test_1_artifacts.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/test_2_artifacts.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/test_3_artifacts.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainThree]);

    renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    fireEvent.click(screen.queryByText('test'));

    await screen.findByText(/hello world from plain content/i);
    await screen.findByText(/hello world from plain second content/i);
    await screen.findByText(/hello world from plain third content/i);

    scope.done();
  });

  it('should render test results v2', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[14])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/test_1_artifacts.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/test_2_artifacts.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/test_3_artifacts.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainThree])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/pytest_results_v2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [testResultsV2]);

    renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    fireEvent.click(screen.queryByText(/test/i));

    await screen.findByText(/hello world from plain content/i);

    await screen.findByText(/hello world from plain second content/i);
    await screen.findByText(/hello world from plain third content/i);

    fireEvent.click(screen.queryByText(/results/i));

    await screen.findByText(/first\/target/i);
    await screen.findByText(/second\/target/i);
    await screen.findByText(/third\/target/i);

    scope.done();
  });

  it('should search test results v2', async () => {
    const user = userEvent.setup();
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[14])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/test_1_artifacts.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/test_2_artifacts.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/test_3_artifacts.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainThree])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/pytest_results_v2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [testResultsV2]);

    renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    fireEvent.click(screen.queryByText(/test/i));

    await screen.findByText(/hello world from plain content/i);

    await screen.findByText(/hello world from plain second content/i);
    await screen.findByText(/hello world from plain third content/i);

    fireEvent.click(screen.queryByText(/results/i));

    await screen.findByText(/first\/target/i);
    await screen.findByText(/second\/target/i);
    await screen.findByText(/third\/target/i);

    // Filters with valid value
    user.type(screen.queryByLabelText(/search file/i), 'first');

    await screen.findByText('first/target');

    await waitFor(() => expect(screen.queryByText(/third\/target/i)).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText(/second\/target/i)).not.toBeInTheDocument());

    // Filters with invalid value
    user.type(screen.queryByLabelText(/search file/i), 'random');

    await waitFor(() => expect(screen.queryByText(/first\/target/i)).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText(/third\/target/i)).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText(/second\/target/i)).not.toBeInTheDocument());

    // Clears filter with no value
    fireEvent.change(screen.queryByLabelText(/search file/i), { target: { value: '' } });

    expect(screen.getByText(/first\/target/i)).toBeInTheDocument();
    expect(screen.getByText(/second\/target/i)).toBeInTheDocument();
    expect(screen.getByText(/third\/target/i)).toBeInTheDocument();

    scope.done();
  });

  it('should render code coverage summary', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[8])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/test_1_artifacts.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/test_2_artifacts.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/test_3_artifacts.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainThree])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/coverage_summary.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [codeCoverage]);

    renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    fireEvent.click(screen.queryByText(/test/i));

    await screen.findByText(/hello world from plain content/i);

    await screen.findByText(/hello world from plain second content/i);
    await screen.findByText(/hello world from plain third content/i);

    fireEvent.click(screen.queryByTitle(/code coverage/i));

    await screen.findByText(/code coverage summary/i);
    await screen.findByText(/counter/i);
    await screen.findByText(/value/i);

    scope.done();
  });

  it('should not render sub tab for artifact with no known content_type', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[1])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree]);

    renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    expect(screen.getByText('lint')).toBeInTheDocument();
    expect(screen.queryByText('random')).not.toBeInTheDocument();

    scope.done();
  });

  it('should render sub tab for random artifact if any artifact has known content_type', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[2])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree]);

    renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    expect(screen.getByText('lint')).toBeInTheDocument();
    expect(screen.getByText('random')).toBeInTheDocument();

    scope.done();
  });

  it('should go back from details to outputs', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[10])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/aggregated_workunit_metrics.json/`)
      .delay(50)
      .reply(200, [workUnitMetrics]);

    const { history } = renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    fireEvent.click(screen.queryByText('Details'));

    await screen.findByText(/some metric two/i);
    await screen.findByText(/some metric three/i);
    await screen.findByText(/some metric four/i);

    expect(screen.getByText('metrics')).toBeInTheDocument();
    expect(screen.getByText('pants_options')).toBeInTheDocument();
    expect(screen.queryByText('lint')).not.toBeInTheDocument();
    expect(screen.queryByText('typecheck')).not.toBeInTheDocument();

    act(() => history.back());

    await screen.findByText('lint');
    await screen.findByText('typecheck');

    expect(screen.queryByText('metrics')).not.toBeInTheDocument();
    expect(screen.queryByText('pants_options')).not.toBeInTheDocument();

    scope.done();
  });

  it('should render targets artifacts', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .delay(100)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[9])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/targets_specs.json/`)
      .delay(50)
      .reply(200, [targets]);

    renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    fireEvent.click(screen.queryByTitle('Targets'));

    await screen.findByText(/folder2\/subfolder2a\/subfolder2b/i);
    await screen.findByText(/folder1\/subfolder1a\/subfolder1b/i);

    scope.done();
  });

  it('should render no targets message if there is no targets', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .delay(100)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[0])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree]);

    renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    fireEvent.click(screen.queryByTitle('Targets'));

    expect(screen.getByText('There are no targets in this build')).toBeInTheDocument();

    scope.done();
  });

  it('should render go back button', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .delay(100)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[0])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree]);

    renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    expect(screen.getByText(/go back/i)).toBeInTheDocument();

    scope.done();
  });

  it('should navigate to build list with no filters', async () => {
    const response: BuildsListResponse = { results: buildsList, total_pages: 3, max_pages: 3, page: 1 };
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .delay(100)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[0])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/`)
      .query({ page: 1 })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/indicators/`)
      .query({ page: 1 })
      .delay(100)
      .reply(200, { indicators: {} })
      .options(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/`)
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    fireEvent.click(screen.queryByText(/go back/i));

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.getByRole('grid')).toBeInTheDocument();
    expect(screen.queryByText(/clear all/i)).not.toBeInTheDocument();

    scope.done();
  });

  it('should navigate to build list with ci filter active', async () => {
    const response: BuildsListResponse = { results: buildsList, total_pages: 3, max_pages: 3, page: 1 };
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .delay(100)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[0])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/`)
      .query({ page: 1, ci: true })
      .delay(100)
      .reply(200, response)
      .get('/api/v1/users/repos/')
      .delay(50)
      .reply(200, repos)
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/indicators/`)
      .query({ page: 1, ci: true })
      .delay(100)
      .reply(200, { indicators: {} })
      .options(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/`)
      .delay(50)
      .query({ field: 'user_api_id,branch,goals,pr' })
      .reply(200, {
        user_api_id: { values: users },
        branch: { values: branches },
        goals: { values: goals },
        pr: { values: [200, 400, 321, 123] },
      });

    renderRetrieveBuild(path, { [`${orgSlug}/${repoSlug}`]: '?ci=1' });

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    fireEvent.click(screen.queryByText(/go back/i));

    await waitFor(() => expect(screen.queryByText('Loading builds...')).not.toBeInTheDocument());

    expect(screen.getByRole('grid')).toBeInTheDocument();
    expect(screen.getByText(/clear all/i)).toBeInTheDocument();
    expect(screen.getByText('CI')).toBeInTheDocument();

    scope.done();
  });

  it('should not render test tabs under other artifacts', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .delay(100)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[8])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree]);

    renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    expect(screen.queryByTitle(/results/i)).not.toBeInTheDocument();
    expect(screen.queryByTitle(/console output/i)).not.toBeInTheDocument();
    expect(screen.queryByTitle(/code coverage/i)).not.toBeInTheDocument();

    scope.done();
  });

  it('should not render outputs subtab when no known content type is present', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .delay(100)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[11])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null });

    renderRetrieveBuild();

    await screen.findByText('Command');

    expect(screen.getByText('There are no outputs in this build')).toBeInTheDocument();
    expect(screen.queryByText('random')).not.toBeInTheDocument();
    expect(screen.queryByText('randomTwo')).not.toBeInTheDocument();

    scope.done();
  });

  it('should not render details subtab when no known content type is present', async () => {
    const user = userEvent.setup();

    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .delay(100)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[12])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null });

    renderRetrieveBuild();

    await screen.findByText('Command');

    // Since all artifacts are run this is expected
    expect(screen.getByText('There are no outputs in this build')).toBeInTheDocument();

    user.click(screen.getByTitle('Details'));

    await screen.findByText('There are no details in this build');

    expect(screen.queryByText('random')).not.toBeInTheDocument();
    expect(screen.queryByText('randomTwo')).not.toBeInTheDocument();

    scope.done();
  });

  it('should render caching information if present', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .delay(100)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[13])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null });

    renderRetrieveBuild();

    await screen.findByText('Command');

    expect(screen.getByText('2 minutes saved')).toBeInTheDocument();
    expect(screen.getByText('50% from cache')).toBeInTheDocument();

    scope.done();
  });

  it('should render failed icons for test and console output tabs', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .delay(100)
      .query({ user_api_id: 'festivus' })
      .reply(200, {
        run_info: { ...buildsMock[8].run_info, build_artifacts: { test: buildsMock[8].run_info.build_artifacts.test } },
      })
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/test_1_artifacts.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/test_2_artifacts.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/test_3_artifacts.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainThree]);

    renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/hello world from plain content/i);
    await screen.findByText(/hello world from plain second content/i);
    await screen.findByText(/hello world from plain third content/i);

    // 3 failures, one for the build itself and 2 for test and console output tabs
    expect(screen.queryAllByTitle('FAILURE')).toHaveLength(3);

    scope.done();
  });

  it('should render run time next to caching information', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .delay(100)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[0])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree]);

    renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    const runTime = durationToFormat(buildsMock[0].run_info.run_time);

    expect(screen.getByText(runTime)).toBeInTheDocument();

    scope.done();
  });

  it('should call downloadFile on workunits selection in download dropdown', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .delay(100)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[0])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree])
      .get('/api/v1/repos/toolchaindev/toolchain/builds/run_id_testing/workunits/')
      .delay(50)
      .reply(200, workunits);

    const string = JSON.stringify(traceData);
    const bytes = new TextEncoder().encode(string);

    renderRetrieveBuild();

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    expect(screen.getByLabelText('Download files')).toBeInTheDocument();

    fireEvent.mouseEnter(screen.getByLabelText('Download files'));

    fireEvent.click(screen.getByText(/workunits/i));

    await waitFor(() => expect(downloadFile).toHaveBeenCalledWith(bytes, `${runId}-workunits.json`));

    scope.done();
  });
  it('should call downloadFile on trace selection in download dropdown', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .delay(100)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[0])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree])
      .get('/api/v1/repos/toolchaindev/toolchain/builds/run_id_testing/trace/')
      .delay(50)
      .reply(200, traceData);

    const string = JSON.stringify(traceData);
    const bytes = new TextEncoder().encode(string);

    renderRetrieveBuild();

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    expect(screen.getByLabelText('Download files')).toBeInTheDocument();

    fireEvent.mouseEnter(screen.getByLabelText('Download files'));

    fireEvent.click(screen.getByText(/trace/i));

    await waitFor(() => expect(downloadFile).toHaveBeenCalledWith(bytes, `${runId}-trace.json`));

    scope.done();
  });

  it('should hide download dropdown on mouse leave', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .delay(100)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[0])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree]);

    renderRetrieveBuild();

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    expect(screen.getByLabelText('Download files')).toBeInTheDocument();

    fireEvent.mouseEnter(screen.getByLabelText('Download files'));

    expect(screen.getByText(/trace/i)).toBeInTheDocument();
    expect(screen.getByText(/workunits/i)).toBeInTheDocument();

    fireEvent.mouseLeave(screen.getByText(/trace/i));

    await waitFor(() => {
      expect(screen.queryByText(/trace/i)).not.toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.queryByText(/workunits/i)).not.toBeInTheDocument();
    });

    scope.done();
  });

  it('should not render download files icon', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .delay(100)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[1])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree]);

    renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    expect(screen.queryByLabelText('Download files')).not.toBeInTheDocument();

    scope.done();
  });

  it('should render free_trial banner', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .delay(100)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[1])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-1.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlain])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-2.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [textPlainTwo])
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/lorem-ipsum-3.json/`)
      .delay(50)
      .query({ user_api_id: 'festivus' })
      .reply(200, [textPlainThree]);

    renderRetrieveBuild();

    await screen.findByText('Command');

    await screen.findByText(/first lint/i);
    await screen.findByText(/second lint/i);
    await screen.findByText(/third lint/i);

    await screen.findByText(/see plan/i);

    expect(
      screen.getByText(`${orgSlug} is in free trial. Upgrade to continue using the service at the end of the trial.`)
    ).toBeInTheDocument();
    expect(screen.getByText(/see plans/i)).toBeInTheDocument();

    scope.done();
  });

  it('should redirect to metrics when no logs are present', async () => {
    const scope = nock(TESTING_HOST)
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/`)
      .delay(100)
      .query({ user_api_id: 'festivus' })
      .reply(200, buildsMock[0])
      .get('/api/v1/users/me/customers/')
      .delay(50)
      .reply(200, { results: orgs, prev: null, next: null })
      .get(`/api/v1/repos/${orgSlug}/${repoSlug}/builds/run_id_testing/artifacts/aggregated_workunit_metrics.json/`)
      .query({ user_api_id: 'festivus' })
      .delay(50)
      .reply(200, [workUnitMetrics]);

    renderRetrieveBuild(paths.buildDetailsType(orgSlug, repoSlug, runId, 'run'), null, '?subTab=logs');

    await screen.findByText(/some metric two/i);
    await screen.findByText(/some metric three/i);
    await screen.findByText(/some metric four/i);

    scope.done();
  });
});
