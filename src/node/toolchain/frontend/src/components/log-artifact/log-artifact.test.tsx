/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';

import LogArtifact from 'components/log-artifact/log-artifact';

import { Artifact, LogArtifactContent } from 'common/interfaces/build-artifacts';
import paths from 'utils/paths';
import render from '../../../tests/custom-render';
import { textLog } from '../../../tests/__fixtures__/artifacts/text-and-log';

const org = 'testorg';
const repo = 'testrepo';
const runId = 'run_id_testing';
const type = 'run';
const defaultPath = paths.buildDetailsType(org, repo, runId, type);

const renderLogArtifact = (
  {
    artifact,
    firstLine,
    lastLine,
  }: { artifact: Artifact<LogArtifactContent>; firstLine?: string; lastLine?: string } = {
    artifact: textLog,
  }
) => {
  const searchParams = new URLSearchParams();
  if (firstLine) {
    searchParams.set('firstLine', firstLine);
  }

  if (lastLine) {
    searchParams.set('lastLine', lastLine);
  }

  return render(
    <Routes>
      <Route path={defaultPath} element={<LogArtifact artifact={artifact} />} />
    </Routes>,
    { wrapperProps: { pathname: defaultPath, search: searchParams.toString() } }
  );
};

describe('<LogArtifat/>', () => {
  it('should show data', async () => {
    const { asFragment } = renderLogArtifact({ artifact: textLog, firstLine: null, lastLine: null });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should show data with one line selected from queryParams', async () => {
    const { asFragment } = renderLogArtifact({ artifact: textLog, firstLine: `1`, lastLine: null });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should show data with multiple lines selected from queryParams', async () => {
    const { asFragment } = renderLogArtifact({ artifact: textLog, firstLine: `1`, lastLine: '2' });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should set new queryParams after selecting one log line', async () => {
    const { history } = renderLogArtifact({ artifact: textLog, firstLine: null, lastLine: null });

    fireEvent.mouseEnter(screen.queryByText('1'));
    fireEvent.mouseDown(screen.queryByText('1'));
    fireEvent.mouseUp(screen.queryByText('1'));

    await waitFor(() => {
      expect(history.location.search).toContain('firstLine=1');
    });
  });

  it('should set new queryParams after selecting multiple log lines', async () => {
    const { history } = renderLogArtifact({ artifact: textLog, firstLine: null, lastLine: null });

    fireEvent.mouseEnter(screen.queryByText('1'));
    fireEvent.mouseDown(screen.queryByText('1'));
    fireEvent.mouseEnter(screen.queryByText('3'));
    fireEvent.mouseUp(screen.queryByText('3'));

    await waitFor(() => expect(history.location.search).toContain('firstLine=1'));
    await waitFor(() => expect(history.location.search).toContain('lastLine=3'));
  });

  it('should switch position of selected lines if starting line is greater then finishing line', async () => {
    const { history } = renderLogArtifact({ artifact: textLog, firstLine: null, lastLine: null });

    fireEvent.mouseEnter(screen.queryByText('3'));
    fireEvent.mouseDown(screen.queryByText('3'));
    fireEvent.mouseEnter(screen.queryByText('1'));
    fireEvent.mouseUp(screen.queryByText('1'));

    await waitFor(() => expect(history.location.search).toContain('firstLine=1'));
    await waitFor(() => expect(history.location.search).toContain('lastLine=3'));
  });

  it('should reset queryParams on mouseUp if selection is not started', async () => {
    const { history } = renderLogArtifact({ artifact: textLog, firstLine: null, lastLine: null });

    fireEvent.mouseEnter(screen.queryByText('1'));
    fireEvent.mouseUp(screen.queryByText('1'));

    await waitFor(() => expect(history.location.search).not.toContain('firstLine'));
    await waitFor(() => expect(history.location.search).not.toContain('lastLine'));
  });

  it('should reset queryParams on mouseUp if selection is not started 2', async () => {
    const { history } = renderLogArtifact({ artifact: textLog, firstLine: null, lastLine: null });

    fireEvent.mouseUp(screen.queryByText('1'));

    await waitFor(() => expect(history.location.search).not.toContain('firstLine'));
    await waitFor(() => expect(history.location.search).not.toContain('lastLine'));
  });
});
