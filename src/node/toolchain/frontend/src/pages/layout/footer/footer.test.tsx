/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { fireEvent, screen } from '@testing-library/react';
import { captureException } from '@sentry/browser';

import AppInitData from 'common/interfaces/appInitData';
import Footer from './footer';
import render from '../../../../tests/custom-render';

const appInitData: AppInitData = {
  assets: { version: 'newest-version-yet', base_path: 'somepath', timestamp: 'someTimestamp' },
  host: 'localhost',
  sentry: {
    dsn: 'yes',
    environment: 'local',
  },
  support_link: null,
};
jest.mock('@sentry/browser');

const renderFooter = () => render(<Footer />);

describe('<Footer />', () => {
  afterEach(() => {
    const initDataElement = document.getElementById('app_init_data');
    if (initDataElement) document.body.removeChild(initDataElement);
    jest.clearAllMocks();
  });

  it('should not render footer', async () => {
    const { asFragment } = renderFooter();

    expect(screen.queryByText(`Version: ${appInitData.assets.version}`)).not.toBeInTheDocument();
    expect(asFragment()).toMatchSnapshot();
  });

  it('should render if appInitData.assets present', async () => {
    const appInitDataElement = document.createElement('script');
    appInitDataElement.id = 'app_init_data';
    appInitDataElement.type = 'text/json';
    appInitDataElement.innerText = btoa(JSON.stringify(appInitData));

    document.body.appendChild(appInitDataElement);

    const { asFragment } = renderFooter();

    expect(screen.getByText(`Version: ${appInitData.assets.version}`)).toBeInTheDocument();
    expect(asFragment()).toMatchSnapshot();
  });

  it('should not render if innerText is missing', async () => {
    const appInitDataElement = document.createElement('script');
    appInitDataElement.id = 'app_init_data';
    appInitDataElement.type = 'text/json';
    appInitDataElement.innerText = null;

    document.body.appendChild(appInitDataElement);

    const { asFragment } = renderFooter();

    expect(screen.queryByText(`Version: ${appInitData.assets.version}`)).not.toBeInTheDocument();
    expect(asFragment()).toMatchSnapshot();
  });

  it('should call captureException on test sentry button click', async () => {
    const appInitDataElement = document.createElement('script');
    appInitDataElement.id = 'app_init_data';
    appInitDataElement.type = 'text/json';
    appInitDataElement.innerText = btoa(JSON.stringify({ ...appInitData, flags: { error_check: true } }));

    document.body.appendChild(appInitDataElement);

    renderFooter();

    fireEvent.click(screen.queryByText(/test sentry/i));

    expect(captureException).toHaveBeenCalledWith(new Error('exception triggered with error_check button'));
  });

  it('should not render test sentry button', async () => {
    const appInitDataElement = document.createElement('script');
    appInitDataElement.id = 'app_init_data';
    appInitDataElement.type = 'text/json';
    appInitDataElement.innerText = btoa(JSON.stringify({ ...appInitData }));

    document.body.appendChild(appInitDataElement);

    renderFooter();

    expect(screen.queryByText(/test sentry/i)).not.toBeInTheDocument();
    expect(screen.getByText(`Version: ${appInitData.assets.version}`)).toBeInTheDocument();
  });

  it('should not render version but render button', async () => {
    const appInitDataElement = document.createElement('script');
    appInitDataElement.id = 'app_init_data';
    appInitDataElement.type = 'text/json';
    appInitDataElement.innerText = btoa(JSON.stringify({ ...appInitData, assets: null, flags: { error_check: true } }));

    document.body.appendChild(appInitDataElement);

    renderFooter();

    expect(screen.getByText(/test sentry/i)).toBeInTheDocument();
    expect(screen.queryByText(`Version: ${appInitData.assets.version}`)).not.toBeInTheDocument();
  });

  it('should not render version or test sentry button', async () => {
    const appInitDataElement = document.createElement('script');
    appInitDataElement.id = 'app_init_data';
    appInitDataElement.type = 'text/json';
    appInitDataElement.innerText = btoa(JSON.stringify({ ...appInitData, assets: null }));

    document.body.appendChild(appInitDataElement);

    renderFooter();

    expect(screen.queryByText(/test sentry/i)).not.toBeInTheDocument();
    expect(screen.queryByText(`Version: ${appInitData.assets.version}`)).not.toBeInTheDocument();
  });

  it('should render support link', async () => {
    const appInitDataElement = document.createElement('script');
    appInitDataElement.id = 'app_init_data';
    appInitDataElement.type = 'text/json';
    appInitDataElement.innerText = btoa(JSON.stringify({ ...appInitData, assets: null }));

    document.body.appendChild(appInitDataElement);

    renderFooter();

    expect(screen.queryByText(/test sentry/i)).not.toBeInTheDocument();
    expect(screen.queryByText(`Version: ${appInitData.assets.version}`)).not.toBeInTheDocument();
  });
});
