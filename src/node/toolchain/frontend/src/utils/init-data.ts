/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { BrowserOptions, init as initSentry } from '@sentry/browser';

import AppInitData from 'common/interfaces/appInitData';

let host: string = '';

/**
 * Init sentry and set host from with config from `index.html`.
 */
export const useInitData: () => void = () => {
  // Init data is base64 encoded JSON string. This is to prevent XSS. More: FrontendApp.get_context_data
  const appInitDataElement: HTMLElement | null = document.getElementById('app_init_data');

  if (!appInitDataElement) {
    return;
  }

  const appInitData: AppInitData = JSON.parse(atob(appInitDataElement.innerText.trim()));

  if (appInitData.host) {
    host = appInitData.host;
  }

  if (appInitData.sentry) {
    // Reduce the object to only include props with value
    const sentryConfig: BrowserOptions = Object.keys(appInitData.sentry).reduce(
      (acc, key) => ({
        ...acc,
        [key]: (appInitData.sentry as any)[key],
      }),
      {}
    );
    sentryConfig.tracesSampleRate = 0;
    sentryConfig.autoSessionTracking = false;
    initSentry(sentryConfig);
  }

  const appBaseElement: HTMLBaseElement = document.getElementById('app_base') as HTMLBaseElement;
  if (appBaseElement) {
    appBaseElement.href = host;
  }
};

/**
 * Get current host.
 */
export const getHost: () => string = () => host;
