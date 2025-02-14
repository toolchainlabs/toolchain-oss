/*
Copyright 2019 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { waitFor } from '@testing-library/react';

import UserAvatar from './user-avatar';
import render from '../../../tests/custom-render';

const renderUserAvatar = ({
  url = null,
  size = 'small',
  userFullName = 'Test User',
}: Partial<React.ComponentProps<typeof UserAvatar>> = {}) =>
  render(<UserAvatar url={url} size={size} userFullName={userFullName} />);

describe('<UserAvatar />', () => {
  it('renders the avatarUrl, if present', async () => {
    const avatarUrl = 'https://avatars1.githubusercontent.com/u/35751794?s=200&v=4';
    const { container } = renderUserAvatar({ url: avatarUrl });

    await waitFor(() => {
      const element = container.querySelector('[src="https://avatars1.githubusercontent.com/u/35751794?s=200&v=4"]');
      if (!element) {
        throw new Error('No image found.');
      }
    });
    expect(container.querySelector('img').src).toBe('https://avatars1.githubusercontent.com/u/35751794?s=200&v=4');
  });

  it('renders small avatar', async () => {
    const avatarUrl = 'https://avatars1.githubusercontent.com/u/35751794?s=200&v=4';
    const { asFragment } = renderUserAvatar({ url: avatarUrl });

    expect(asFragment()).toMatchSnapshot();
  });

  it('renders large avatar', async () => {
    const avatarUrl = 'https://avatars1.githubusercontent.com/u/35751794?s=200&v=4';
    const { asFragment } = renderUserAvatar({ url: avatarUrl, size: 'large' });

    expect(asFragment()).toMatchSnapshot();
  });
});
