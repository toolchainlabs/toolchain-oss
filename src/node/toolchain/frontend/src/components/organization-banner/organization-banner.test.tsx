/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

/*
Copyright © 2021 Toolchain Labs, Inc. All rights reserved.

Toolchain Labs, Inc. CONFIDENTIAL

This file includes unpublished proprietary source code of Toolchain Labs, Inc.
The copyright notice above does not evidence any actual or intended publication of such source code.
Disclosure of this source code or any related proprietary information is strictly prohibited without
the express written permission of Toolchain Labs, Inc.
*/

import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { screen } from '@testing-library/react';

import OrganizationBanner from './organization-banner';
import render from '../../../tests/custom-render';
import CustomerStatus from 'common/enums/CustomerStatus';

const org = 'toolchaindev';
const url = 'https://docs.toolchain.com/';

const renderOrganizationBanner = ({
  status = null,
  name = 'Toolchain',
  docsUrl = null,
}: Partial<React.ComponentProps<typeof OrganizationBanner>> = {}) =>
  render(
    <Routes>
      <Route
        path="/organizations/:orgSlug"
        element={<OrganizationBanner status={status} name={name} docsUrl={docsUrl} />}
      />
    </Routes>,
    { wrapperProps: { pathname: `/organizations/${org}` } }
  );

describe('<OrganizationBanner />', () => {
  it('should render free_trial banner', async () => {
    const { asFragment } = renderOrganizationBanner({ status: CustomerStatus.FREE_TRIAL });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render limited banner', async () => {
    const { asFragment } = renderOrganizationBanner({ status: CustomerStatus.LIMITED });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render no builds banner', async () => {
    const { asFragment } = renderOrganizationBanner({ status: 'noBuilds', docsUrl: url });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render no builds banner with link that has target _blank', async () => {
    renderOrganizationBanner({ status: 'noBuilds', docsUrl: url });

    expect(screen.getByText(/instructions/i).closest('a')).toHaveProperty('href', url);
    expect(screen.getByText(/instructions/i).closest('a')).toHaveProperty('target', '_blank');
  });
});
