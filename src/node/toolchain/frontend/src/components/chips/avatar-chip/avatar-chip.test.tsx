/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';

import AvatarChip from './avatar-chip';
import render from '../../../../tests/custom-render';

const renderAvatarChip = ({
  text = 'username',
  avatar = null,
  size,
  variant,
}: Partial<React.ComponentProps<typeof AvatarChip>> = {}) =>
  render(<AvatarChip text={text} avatar={avatar} size={size} variant={variant} />);

describe('<AvatarChip />', () => {
  it('should render with passed avatar', () => {
    const { asFragment } = renderAvatarChip({
      avatar: 'data:image/gif;base64,R0lGODlhAQABAIAAAMLCwgAAACH5BAAAAAAALAAAAAABAAEAAAICRAEAOw==',
    });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render with default avatar', () => {
    const { asFragment } = renderAvatarChip({
      avatar: null,
    });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render small chip', () => {
    const { asFragment } = renderAvatarChip({ size: 'small' });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render medium chip', () => {
    const { asFragment } = renderAvatarChip({ size: 'medium' });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render default chip', () => {
    const { asFragment } = renderAvatarChip({ variant: 'filled' });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render outlined chip', () => {
    const { asFragment } = renderAvatarChip({ variant: 'outlined' });

    expect(asFragment()).toMatchSnapshot();
  });
});
