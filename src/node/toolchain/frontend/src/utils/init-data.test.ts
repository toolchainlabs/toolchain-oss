/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { init as initSentry } from '@sentry/browser';
import { useInitData, getHost } from 'utils/init-data';

jest.mock('@sentry/browser');

describe('useInitData', () => {
  let appInitDataElement: HTMLScriptElement;
  let appBaseElement: HTMLBaseElement;
  const host = 'http://localhost';
  const sentry = {
    dsn: 'abc.example.com',
    environment: 'test',
    release: 'example-release',
  };

  beforeEach(() => {
    appInitDataElement = document.createElement('script');
    appInitDataElement.id = 'app_init_data';
    appInitDataElement.type = 'text/json';

    document.body.appendChild(appInitDataElement);

    appBaseElement = document.createElement('base');
    appBaseElement.id = 'app_base';
    appBaseElement.href = '/';

    document.querySelector('head').appendChild(appBaseElement);
  });

  afterEach(() => {
    document.body.removeChild(appInitDataElement);
    document.querySelector('head').removeChild(appBaseElement);
  });

  it("shouldn't fail if there is no script element", () => {
    appInitDataElement.id = 'lorem-ipsum';

    expect(() => {
      useInitData();
    }).not.toThrowError();
  });

  it("shouldn't set host and init sentry if no data", () => {
    appInitDataElement.innerText = btoa(JSON.stringify({}));

    useInitData();

    expect(getHost()).toBe('');
    expect(initSentry).not.toHaveBeenCalled();
  });

  it('should set host and init sentry', () => {
    appInitDataElement.innerText = btoa(
      JSON.stringify({
        host,
        sentry,
      })
    );

    useInitData();

    expect(getHost()).toBe(host);
    expect(initSentry).toHaveBeenCalledWith({
      dsn: sentry.dsn,
      environment: sentry.environment,
      release: 'example-release',
      tracesSampleRate: 0,
      autoSessionTracking: false,
    });
  });

  it('should init sentry without release', () => {
    const sentryObj = {
      dns: sentry.dsn,
      environment: sentry.environment,
    };

    appInitDataElement.innerText = btoa(JSON.stringify({ sentry: sentryObj }));

    useInitData();

    expect(initSentry).toHaveBeenCalledWith({
      dsn: sentry.dsn,
      environment: sentry.environment,
      release: 'example-release',
      tracesSampleRate: 0,
      autoSessionTracking: false,
    });
  });

  it("shouldn't fail if there is no base element", () => {
    appInitDataElement.innerText = btoa(
      JSON.stringify({
        host,
        sentry,
      })
    );
    appBaseElement.id = 'lorem-ipsum';

    expect(() => {
      useInitData();
    }).not.toThrowError();
  });

  it('should set base href', () => {
    appInitDataElement.innerText = btoa(
      JSON.stringify({
        host,
        sentry,
      })
    );

    useInitData();

    expect(appBaseElement.href).toBe(`${host}/`);
  });
});
