/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen } from '@testing-library/react';

import OrganizationIcon, { getFirstLettersFromSlug } from './organization-icon';
import render from '../../../tests/custom-render';

const renderOrganizationIcon = ({
  slug = 'some-org',
  url = 'https://example.com/avatar-icon.jpg',
}: Partial<React.ComponentProps<typeof OrganizationIcon>> = {}) =>
  render(<OrganizationIcon slug={slug} url={url} size="small" />);

describe('<OrganizationIcon />', () => {
  it('should render according to snapshot', () => {
    const { asFragment } = renderOrganizationIcon({});
    expect(asFragment()).toMatchSnapshot();
  });

  it('should display slug letters if there is no logo url', () => {
    const orgSlug = 'My org slug';
    renderOrganizationIcon({ slug: orgSlug, url: '' });
    const slugLetters = getFirstLettersFromSlug(orgSlug);
    expect(screen.getByText(slugLetters)).toBeInTheDocument();
  });
});
