/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { isAfter } from 'utils/datetime-formats';

const tokens = [
  {
    id: 'AEn89bZgC8UKQJYEWq8N9e',
    issued_at: '2021-06-22T21:08:33.963425+00:00',
    expires_at: '2021-12-19T21:08:33.961987+00:00',
    last_seen: '2021-06-29T17:32:24.476704+00:00',
    description: 'no soup for you',
    state: 'active',
    can_revoke: true,
    permissions: ['buildsense', 'cache_ro', 'cache_rw'],
    repo: {
      id: 'K2aDLFAzf9LE7oKgMpxxBA',
      name: 'Toolchain[DEV]',
      slug: 'toolchain',
    },
    customer: {
      id: 'hdt2hniUXemsaHDuiBap4B',
      name: 'Seinfeld Enterprises[DEV]',
      slug: 'seinfeld',
    },
  },
  {
    id: 'n9UY4zWdwGjkkJYGciKeKs',
    issued_at: '2021-06-17T22:10:39.245431+00:00',
    expires_at: '2021-12-14T22:10:39.243108+00:00',
    last_seen: '2021-06-22T21:08:32.907196+00:00',
    description: 'test-new-token-dev-mac',
    state: 'active',
    can_revoke: true,
    permissions: [''],
  },
  {
    id: 'aoCY8HrLLgegTt98chQ6dU',
    issued_at: '2021-06-05T00:31:30.461440+00:00',
    expires_at: '2021-12-02T00:31:30.459792+00:00',
    last_seen: null,
    description: 'Ashers-MacBook-Pro.local [for CI]',
    state: 'active',
    can_revoke: true,
    permissions: [],
  },
  {
    id: '29XahgkTbF3wfdmxVn6Svq',
    issued_at: '2021-06-05T00:31:06.125070+00:00',
    expires_at: '2021-12-02T00:31:06.123557+00:00',
    last_seen: '2021-06-17T22:10:31.582256+00:00',
    description: 'Ashers-MacBook-Pro.local',
    state: 'active',
    can_revoke: true,
    permissions: [],
  },
  {
    id: 'MpgRoduyg9vdJZjk7pofP9',
    issued_at: '2021-06-05T00:30:43.602261+00:00',
    expires_at: '2021-12-02T00:30:43.600137+00:00',
    last_seen: '2021-06-05T00:31:02.036563+00:00',
    description: 'jerry',
    state: 'active',
    can_revoke: false,
    permissions: [],
  },
];

const sortedTokens = tokens.sort((a, b) => (isAfter((a as any).asc, (b as any).asc) ? 1 : -1));

export default sortedTokens;
