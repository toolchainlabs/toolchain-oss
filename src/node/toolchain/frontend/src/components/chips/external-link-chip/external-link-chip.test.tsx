/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';

import ExternalLinkChip from './external-link-chip';
import render from '../../../../tests/custom-render';

const renderExternalLinkChip = ({
  text = 'random',
  link = 'www.random.com',
  icon = null,
}: Partial<React.ComponentProps<typeof ExternalLinkChip>> = {}) =>
  render(<ExternalLinkChip text={text} link={link} icon={icon} />);

describe('<ExternalLinkChip />', () => {
  it('should render random link and icon chip', () => {
    const { asFragment } = renderExternalLinkChip();

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render github link and icon chip', () => {
    const { asFragment } = renderExternalLinkChip({ text: 'github', link: 'www.github.com', icon: 'github' });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render travis-ci link and icon chip', () => {
    const { asFragment } = renderExternalLinkChip({ text: 'travis-ci', link: 'www.travis-ci.com', icon: 'travis-ci' });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render circle-ci link and icon chip', () => {
    const { asFragment } = renderExternalLinkChip({ text: 'circleci', link: 'www.circleci.com', icon: 'circleci' });

    expect(asFragment()).toMatchSnapshot();
  });
});
