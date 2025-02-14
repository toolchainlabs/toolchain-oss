/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen } from '@testing-library/react';

import VisitScmButton from './visit-scm-button';
import render from '../../../tests/custom-render';

const githubScm = 'github';
const bitBucketScm = 'bitbucket';
const bitbucketLink = 'https://bitbucket.org/toolchainlabs/';
const githubLink = 'https://github.com/toolchainlabs/';

const renderVisitScmButton = ({
  url = githubLink,
  scm = githubScm,
}: Partial<React.ComponentProps<typeof VisitScmButton>> = {}) => render(<VisitScmButton url={url} scm={scm} />);

describe('<VisitScmButton />', () => {
  it('should render the component', () => {
    const { asFragment } = renderVisitScmButton();

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render github icon', () => {
    renderVisitScmButton();

    expect(screen.getByAltText('GitHub link icon')).toBeInTheDocument();
  });

  it('should render bitbucket icon', () => {
    renderVisitScmButton({ scm: bitBucketScm });

    expect(screen.getByAltText('Bitbucket link icon')).toBeInTheDocument();
  });

  it('should link to bitbucket', () => {
    renderVisitScmButton({ scm: bitBucketScm, url: bitbucketLink });

    expect(screen.queryByAltText('Bitbucket link icon').closest('a')).toHaveAttribute('href', bitbucketLink);
  });

  it('should link to github', () => {
    renderVisitScmButton({ scm: githubScm, url: githubLink });

    expect(screen.queryByAltText('GitHub link icon').closest('a')).toHaveAttribute('href', githubLink);
  });
});
