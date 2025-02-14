/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen, fireEvent } from '@testing-library/react';

import { useOrgAndRepoContext } from './org-repo-store';
import render from '../../tests/custom-render';

type TestOrgAndRepoStoreProps = {
  repoValue: string;
  orgValue: string;
};

const TestOrgAndRepoStore = ({ repoValue, orgValue }: TestOrgAndRepoStoreProps) => {
  const { org, setOrg, repo, setRepo } = useOrgAndRepoContext();

  return (
    <>
      <button data-testid="setOrgButton" aria-label="setOrg" onClick={() => setOrg(orgValue)} type="button" />
      {org && <div data-testid="org">{org}</div>}
      <button data-testid="setRepoButton" aria-label="setRepo" onClick={() => setRepo(repoValue)} type="button" />
      {repo && <div data-testid="repo">{repo}</div>}
    </>
  );
};

const renderTestOrgAndRepoStore = ({ repoValue = 'toolchain', orgValue = 'seinfeld' }: TestOrgAndRepoStoreProps) =>
  render(<TestOrgAndRepoStore repoValue={repoValue} orgValue={orgValue} />);

const repoName = 'nikolasRepo';
const orgName = 'nikola';

describe('useOrgAndRepoStore', () => {
  it('should not render repo or org by default', () => {
    renderTestOrgAndRepoStore({ repoValue: repoName, orgValue: orgName });

    expect(screen.queryByTestId('org')).not.toBeInTheDocument();
    expect(screen.queryByTestId('repo')).not.toBeInTheDocument();
  });

  it('should render repo on setRepoButton click', async () => {
    renderTestOrgAndRepoStore({ repoValue: repoName, orgValue: orgName });

    const button = screen.queryByTestId('setRepoButton');

    fireEvent.click(button);

    await screen.findByTestId('repo');
    await screen.findByText(repoName);
  });

  it('should render org on setOrgButton click', async () => {
    renderTestOrgAndRepoStore({ repoValue: repoName, orgValue: orgName });

    const button = screen.queryByTestId('setOrgButton');

    fireEvent.click(button);

    await screen.findByTestId('org');
    await screen.findByText(orgName);
  });
});
