/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import * as Sentry from '@sentry/react';
import { BrowserTracing } from '@sentry/tracing';
import { Integration } from '@sentry/types';
import { createRoot } from 'react-dom/client';
import App from './App';

Sentry.init({
  dsn: 'https://a49a32f459944e8eb741d1244bc8d1cd@o265975.ingest.sentry.io/6249632',
  integrations: [new BrowserTracing() as Integration],
  tracesSampleRate: 0,
  normalizeDepth: 10,
  enabled: process.env.NODE_ENV !== 'development',
});

const container = document.getElementById('app');
// eslint-disable-next-line @typescript-eslint/no-non-null-assertion
const root = createRoot(container!);

root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
