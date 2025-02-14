/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen, fireEvent } from '@testing-library/react';

import { AppVersionProvider, useAppVersionContext } from './app-version-store';
import render from '../../tests/custom-render';

const TestAppVersionStore = ({ version = null, serverVersion = null }: { version: string; serverVersion: string }) => {
  const { setAppVersion, setServerAppVersion, appVersion, serverAppVersion } = useAppVersionContext();

  return (
    <>
      <button aria-label="setAppVersion" onClick={() => setAppVersion(version)} type="button" />
      {appVersion && <div data-testid="appVersion">{appVersion}</div>}
      <button aria-label="setServerAppVersion" onClick={() => setServerAppVersion(serverVersion)} type="button" />
      {serverAppVersion && <div data-testid="serverAppVersion">{serverAppVersion}</div>}
    </>
  );
};

const renderTestAppVersionStore = (appVersionProp?: string, serverAppVersionProp?: string) =>
  render(
    <AppVersionProvider>
      <TestAppVersionStore version={appVersionProp} serverVersion={serverAppVersionProp} />
    </AppVersionProvider>
  );

describe('useAppVersionStore', () => {
  it('should not render appVersion by default', () => {
    renderTestAppVersionStore();

    expect(screen.queryByTestId('appVersion')).not.toBeInTheDocument();
  });

  it('should not render serverAppVersion by default', () => {
    renderTestAppVersionStore();

    expect(screen.queryByTestId('serverAppVersion')).not.toBeInTheDocument();
  });

  it('should set app version on click', () => {
    const versionName = 'newVersion';
    renderTestAppVersionStore(versionName);

    fireEvent.click(screen.getByLabelText('setAppVersion'));

    expect(screen.queryByTestId('appVersion').innerHTML).toContain(versionName);
  });

  it('should set app version on click', () => {
    const versionName = 'newVersion';
    renderTestAppVersionStore(null, versionName);

    fireEvent.click(screen.getByLabelText('setServerAppVersion'));

    expect(screen.queryByTestId('serverAppVersion').innerHTML).toContain(versionName);
  });
});
