/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';

import { dateTimeAndTimeFromNowLocal, durationToFormat } from 'utils/datetime-formats';
import RunType from 'common/enums/RunType';
import paths from 'utils/paths';
import Details from './details-pane';
import buildsList from '../../../tests/__fixtures__/builds-list';
import render from '../../../tests/custom-render';

const defaultData = buildsList[0];
const ciData = buildsList[2];
const orgSlug = 'toolchainLabs';
const repoSlug = 'toolchain';
const runId = 'someRandomId';
const ciBuildLinks = [
  { icon: 'github', text: 'github text', link: 'https://github.com/' },
  { icon: 'travis-ci', text: 'travis text', link: 'https://travis-ci.com/' },
  { icon: 'circleci', text: 'circle text', link: 'https://circleci.com/' },
  { icon: 'random-ci', text: 'random text', link: 'https://random-ci.com/' },
];
const prTitle = 'Human, it’s human to be moved by a fragrance.';
const prNumber = 13;

const renderBuildDetails = ({ data = defaultData }: Partial<React.ComponentProps<typeof Details>> = {}) =>
  render(
    <Routes>
      <Route path="/organizations/:orgSlug/repos/:repoSlug/builds/:runId/" element={<Details data={data} />} />
    </Routes>,
    { wrapperProps: { pathname: paths.buildDetails(orgSlug, repoSlug, runId) } }
  );

describe('<Details />', () => {
  it('should render the component', () => {
    const { asFragment } = renderBuildDetails();

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render pants command', () => {
    renderBuildDetails();

    expect(screen.getByText('some command a')).toBeInTheDocument();
  });

  it('should toggle show more details', async () => {
    renderBuildDetails();

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));

    expect(screen.getByText('STARTED')).toBeInTheDocument();

    fireEvent.click(screen.queryByText('SHOW LESS INFO'));

    await waitFor(() => expect(screen.queryByText('STARTED')).not.toBeInTheDocument());
  });

  it('should render started date', async () => {
    renderBuildDetails();

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));

    const dateTimeText = dateTimeAndTimeFromNowLocal(defaultData.datetime);

    expect(screen.getByText(dateTimeText)).toBeInTheDocument();
  });

  it('should render duration time', async () => {
    renderBuildDetails();

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));

    const durationTimeText = durationToFormat(defaultData.run_time);

    expect(screen.getByText(durationTimeText)).toBeInTheDocument();
  });

  it('should render not calculated if no run_time time', async () => {
    renderBuildDetails({ data: { ...defaultData, run_time: null } });

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));

    expect(screen.getByText('Unknown')).toBeInTheDocument();
  });

  it('should render all goals', async () => {
    renderBuildDetails();

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));

    defaultData.goals.forEach(goal => expect(screen.getByText(goal)).toBeInTheDocument());
  });

  it('should render repo name and link to builds', async () => {
    renderBuildDetails();

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));

    expect(screen.getByText(defaultData.repo_slug)).toBeInTheDocument();
    expect(screen.queryByText(defaultData.repo_slug).closest('a')).toHaveAttribute(
      'href',
      paths.builds(orgSlug, defaultData.repo_slug)
    );
  });

  it('should render user and link to builds with user query param', async () => {
    renderBuildDetails();

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));

    expect(screen.getByText(defaultData.user.full_name)).toBeInTheDocument();
    expect(screen.queryByText(defaultData.user.full_name).closest('a')).toHaveAttribute(
      'href',
      `${paths.builds(orgSlug, defaultData.repo_slug)}?user=${defaultData.user.username}`
    );
  });

  it('should render title for local environment data', async () => {
    renderBuildDetails();

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));

    expect(screen.getByText('Local machine info')).toBeInTheDocument();
  });

  it('should render machine name', async () => {
    renderBuildDetails();

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));

    expect(screen.getByText(defaultData.machine)).toBeInTheDocument();
  });

  it('should render branch name', async () => {
    renderBuildDetails();

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));

    expect(screen.getByText(defaultData.branch)).toBeInTheDocument();
  });

  it('should render no branch name text', async () => {
    renderBuildDetails({ data: { ...defaultData, branch: null } });

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));

    expect(screen.getByText('No branch reported')).toBeInTheDocument();
  });

  it('should render title for ci environment data', async () => {
    renderBuildDetails({ data: ciData });

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));

    expect(screen.getByText('CI info')).toBeInTheDocument();
  });

  it('should render run type as branch', async () => {
    renderBuildDetails({ data: { ...ciData, ci_info: { ...ciData.ci_info, run_type: RunType.BRANCH } } });

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));

    expect(screen.getByText('Branch')).toBeInTheDocument();
  });

  it('should render run type as pull request', async () => {
    renderBuildDetails({ data: ciData });

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));

    expect(screen.getByText('Pull Request')).toBeInTheDocument();
  });

  it('should render job name', async () => {
    renderBuildDetails({ data: ciData });

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));

    expect(screen.getByText(ciData.ci_info.job_name)).toBeInTheDocument();
  });

  it('should render build number', async () => {
    renderBuildDetails({ data: ciData });

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));

    expect(screen.getByText(ciData.ci_info.build_num)).toBeInTheDocument();
  });

  it('should render branch name for ci', async () => {
    renderBuildDetails({ data: ciData });

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));

    expect(screen.getByText(ciData.branch)).toBeInTheDocument();
  });

  it('should render context github link, text and icon', async () => {
    const link = ciBuildLinks[0];
    renderBuildDetails({
      data: {
        ...ciData,
        ci_info: {
          ...ciData.ci_info,
          links: [link],
        },
      },
    });

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));

    expect(screen.getByText(link.text)).toBeInTheDocument();
    expect(screen.queryByText(link.text).closest('a')).toHaveAttribute('href', link.link);
    expect(screen.getByAltText('GitHub link icon')).toBeInTheDocument();
  });

  it('should render context travis link, text and icon', async () => {
    const travisLink = ciBuildLinks[1];
    renderBuildDetails({
      data: {
        ...ciData,
        ci_info: {
          ...ciData.ci_info,
          links: [travisLink],
        },
      },
    });

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));

    expect(screen.getByText(travisLink.text)).toBeInTheDocument();
    expect(screen.queryByText(travisLink.text).closest('a')).toHaveAttribute('href', travisLink.link);
    expect(screen.getByAltText('Travis CI link icon')).toBeInTheDocument();
  });

  it('should render context circle link, text and icon', async () => {
    const link = ciBuildLinks[2];
    renderBuildDetails({
      data: {
        ...ciData,
        ci_info: {
          ...ciData.ci_info,
          links: [link],
        },
      },
    });

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));

    expect(screen.getByText(link.text)).toBeInTheDocument();
    expect(screen.queryByText(link.text).closest('a')).toHaveAttribute('href', link.link);
    expect(screen.getByAltText('Circle ci link icon')).toBeInTheDocument();
  });

  it('should render context circle link, text and icon', async () => {
    const link = ciBuildLinks[3];
    renderBuildDetails({
      data: {
        ...ciData,
        ci_info: {
          ...ciData.ci_info,
          links: [link],
        },
      },
    });

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));

    expect(screen.getByText(link.text)).toBeInTheDocument();
    expect(screen.queryByText(link.text).closest('a')).toHaveAttribute('href', link.link);
    expect(screen.getByAltText('External link icon')).toBeInTheDocument();
  });

  it('should render PR title as a link to build list page filtered by PR number', () => {
    renderBuildDetails({
      data: {
        ...ciData,
        ci_info: {
          ...ciData.ci_info,
          pull_request: prNumber,
        },
        title: prTitle,
      },
    });

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));
    expect(screen.getByText(prTitle)).toBeInTheDocument();
    expect(screen.queryByText(prTitle).closest('a')).toHaveAttribute(
      'href',
      `${paths.builds(orgSlug, defaultData.repo_slug)}?pr=${prNumber}`
    );
  });

  it('should not render PR title it there is no title in data object', () => {
    renderBuildDetails({
      data: {
        ...ciData,
        ci_info: {
          ...ciData.ci_info,
          pull_request: prNumber,
        },
      },
    });

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));
    expect(screen.queryByText(prTitle)).not.toBeInTheDocument();
  });

  it('should render PR title as a text if there is no pr number', () => {
    renderBuildDetails({
      data: {
        ...ciData,
        ci_info: {
          ...ciData.ci_info,
          pull_request: undefined,
        },
        title: prTitle,
      },
    });

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));

    expect(screen.queryByText(prTitle)).not.toHaveAttribute('href');
  });

  it('should render platform info', () => {
    renderBuildDetails({
      data: defaultData,
    });

    const {
      python_implementation: pythonImplementation,
      python_version: pythonVersion,
      architecture,
      os,
      os_release: osRelease,
      cpu_count: cpuCount,
      mem_bytes: memBytes,
    } = defaultData.platform;

    const memGigabyte = (memBytes / (1024 * 1024 * 1024)).toFixed(0);

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));

    expect(
      screen.getByText(`${pythonImplementation} ${pythonVersion} on ${architecture} ${os} ${osRelease}`, {
        exact: false,
      })
    ).toBeInTheDocument();
    expect(
      screen.getByText(`(${cpuCount} cores, ${memGigabyte}GB RAM)`, {
        exact: false,
      })
    ).toBeInTheDocument();
  });

  it('should render platform info not available', () => {
    renderBuildDetails({
      data: { ...defaultData, platform: null },
    });

    fireEvent.click(screen.queryByText('SHOW MORE INFO'));

    expect(screen.getByText(/not available/i)).toBeInTheDocument();
  });
});
