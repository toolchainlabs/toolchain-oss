/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen } from '@testing-library/react';
import { Routes, Route } from 'react-router-dom';

import paths from 'utils/paths';
import BreadCrumbs from './breadcrumbs';
import render from '../../../tests/custom-render';

const organization = 'ToolchainLabs';
const repository = 'Buildsense';

const renderBreadcrumbs = ({
  org = organization,
  repo = repository,
}: Partial<React.ComponentProps<typeof BreadCrumbs>> = {}) =>
  render(
    <Routes>
      <Route path="/" element={<BreadCrumbs org={org} repo={repo} />} />
    </Routes>,
    { wrapperProps: { pathname: '/' } }
  );

describe('<BreadCrumbs />', () => {
  it('should render the component', () => {
    const { asFragment } = renderBreadcrumbs();

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render organization', () => {
    renderBreadcrumbs({ repo: null });

    expect(screen.getByText(organization)).toBeInTheDocument();
    expect(screen.queryByText(repository)).not.toBeInTheDocument();
  });

  it('should render organization and repository', () => {
    renderBreadcrumbs();

    expect(screen.getByText(organization)).toBeInTheDocument();
    expect(screen.getByText(repository)).toBeInTheDocument();
  });

  it('should capitalize organization and repository text', () => {
    renderBreadcrumbs({ org: 'firstOrg', repo: 'firstRepo' });

    expect(screen.getByText('FirstOrg')).toBeInTheDocument();
    expect(screen.getByText('FirstRepo')).toBeInTheDocument();
  });

  it('should contain link to organization', () => {
    renderBreadcrumbs();

    expect(screen.queryByText(organization).closest('a')).toHaveAttribute('href', paths.organization(organization));
  });
  it('should contain link to builds with default me param', () => {
    renderBreadcrumbs();

    expect(screen.queryByText(repository).closest('a')).toHaveAttribute(
      'href',
      `${paths.builds(organization, repository)}?user=me`
    );
  });
});
