/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen, fireEvent } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { Routes, Route } from 'react-router-dom';

import render from '../../../../tests/custom-render';
import RepoCard from './repo-card';
import paths from 'utils/paths';
import queryClient from '../../../../tests/queryClient';

const activeRepo: React.ComponentProps<typeof RepoCard> = {
  name: 'toolchain',
  slug: 'toolchain',
  isActive: true,
  orgSlug: 'toolchaindev',
  isManagingRepos: false,
  isAdmin: false,
};
const inActiveRepo: React.ComponentProps<typeof RepoCard> = {
  name: 'toolchain',
  slug: 'toolchain',
  isActive: false,
  orgSlug: 'toolchaindev',
  isManagingRepos: false,
  isAdmin: false,
};

const renderRepoCard = ({
  name,
  slug,
  isActive,
  orgSlug,
  isManagingRepos,
  isAdmin,
}: Partial<React.ComponentProps<typeof RepoCard>> = {}) =>
  render(
    <QueryClientProvider client={queryClient}>
      <Routes>
        <Route
          path="/organizations/:orgSlug/"
          element={
            <RepoCard
              name={name}
              slug={slug}
              isActive={isActive}
              orgSlug={orgSlug}
              isManagingRepos={isManagingRepos}
              isAdmin={isAdmin}
            />
          }
        />
      </Routes>
    </QueryClientProvider>,
    { wrapperProps: { pathname: paths.organization(orgSlug) } }
  );

describe('<RepoCard />', () => {
  it('should render active repo-card component', async () => {
    const { asFragment } = renderRepoCard(activeRepo);

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render inactive repo-card component', async () => {
    const { asFragment } = renderRepoCard(inActiveRepo);

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render activate button', async () => {
    const { asFragment } = renderRepoCard({ ...inActiveRepo, isAdmin: true, isManagingRepos: true });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render deactivate button', async () => {
    const { asFragment } = renderRepoCard({ ...activeRepo, isAdmin: true, isManagingRepos: true });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render deactivate button on hover', async () => {
    renderRepoCard({ ...inActiveRepo, isAdmin: true });

    fireEvent.mouseEnter(screen.queryAllByText('toolchain')[0]);

    expect(screen.getByText('ACTIVATE')).toBeInTheDocument();

    fireEvent.mouseLeave(screen.queryAllByText('toolchain')[0]);

    expect(screen.queryByText('ACTIVATE')).not.toBeInTheDocument();
  });

  it('should render deactivate button on hover', async () => {
    renderRepoCard(inActiveRepo);

    fireEvent.mouseEnter(screen.queryAllByText('toolchain')[0]);

    expect(screen.queryByText('ACTIVATE')).not.toBeInTheDocument();
  });
});
