/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { fireEvent, screen } from '@testing-library/react';

import generateUrl from 'utils/url';
import backendPaths from 'utils/backend-paths';
import { getHost } from 'utils/init-data';
import ImpersonationBanner from './impersonation-banner';
import render from '../../../tests/custom-render';

const TESTING_HOST = 'http://localhost';
const initData = {
  expiry: '2021-06-18T17:03:23.188832',
  impersonator_full_name: 'Christopher Neugebauer',
  impersonator_username: 'chrisjrn',
  user_full_name: 'John Clarke',
  user_username: 'john_clarke',
};
const assignMock = jest.fn();
jest.mock('utils/init-data', () => ({
  getHost: () => TESTING_HOST,
}));

const renderImpersonationBanner = ({
  impersonationData = initData,
}: Partial<React.ComponentProps<typeof ImpersonationBanner>> = {}) =>
  render(<ImpersonationBanner impersonationData={impersonationData} />);

describe('<ImpersonationBanner />', () => {
  const { location } = window;

  beforeAll(() => {
    delete window.location;
    (window.location as any) = { assign: assignMock };
  });

  afterAll(() => {
    window.location = location;
  });

  it('should render component', async () => {
    const { asFragment } = renderImpersonationBanner();

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render string with full names of user and impersonator', async () => {
    renderImpersonationBanner();

    expect(
      screen.getByText(
        `${initData.impersonator_username} (${initData.impersonator_full_name}) is ghosting ${initData.user_username} (${initData.user_full_name})`
      )
    ).toBeInTheDocument();
  });

  it('should not render string with full names of user and impersonator', async () => {
    renderImpersonationBanner({ impersonationData: { ...initData, impersonator_full_name: '', user_full_name: '' } });

    expect(
      screen.getByText(`${initData.impersonator_username} is ghosting ${initData.user_username}`)
    ).toBeInTheDocument();
  });

  it('should sign out on button click', async () => {
    renderImpersonationBanner();

    fireEvent.click(screen.queryByText(/quit ghosting mode/i));

    expect(assignMock).toHaveBeenCalledWith(generateUrl(backendPaths.users_ui.LOGOUT, getHost()));
  });
});
