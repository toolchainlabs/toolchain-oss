/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { WorkerToken, WorkerTokenState } from 'common/interfaces/worker-tokens';

const data: { tokens: WorkerToken[] } = {
  tokens: [
    {
      id: '5GykLWhYJtoj9qHNjtuf3Y',
      created_at: '2022-12-13T09:37:49.098467+00:00',
      state: WorkerTokenState.ACTIVE,
      description: 'Created by npervic',
      token: 'pXtrfh3uLv5c1l40bmT6h567uUxYPYawrVbC9gnK6JjdJvO5biWO2FFGRlJZx846',
    },
    {
      id: 'ZJtokW3TyBQAkscsAeHLmK',
      created_at: '2022-12-13T09:37:48.948791+00:00',
      state: WorkerTokenState.ACTIVE,
      description: 'ddddddddd',
      token: 'dzXsgzu3Ylc5gnFIAiGnF6q6rtTdDNUdd23hsYwfZIhTYDNr0ll0EdwhK2ZdddxG',
    },
    {
      id: 'hrPDdPxUM8UK2akAGguzfs',
      created_at: '2022-12-13T09:37:47.731616+00:00',
      state: WorkerTokenState.INACTIVE,
      description: 'Created by npervic',
    },
    {
      id: 'g6Mhqd9qDafAgvCZ4ZfY7T',
      created_at: '2022-12-13T09:37:47.538789+00:00',
      state: WorkerTokenState.ACTIVE,
      description: 'eeeeeeeeee',
      token: '36eY3PLOk8ztuflJV5O48XVcj3Acsp1DNFN9kJrwnN8V0c9vkmP6ewYP0wxCGuou',
    },
    {
      id: 'nWvmhM2KtsUVT8tThYXxGz',
      created_at: '2022-12-13T09:37:47.406714+00:00',
      state: WorkerTokenState.ACTIVE,
      description: 'Created by npervic',
      token: 'sf5jtOb4Av876qFfrukO4skMnamGvPUPcBJvxFJKGhcTFNKmom1o56EBXPgp3BIT',
    },
    {
      id: 'jP8rMumhBKm6ihCq68TDuA',
      created_at: '2022-12-19T00:00:00.406714+00:00',
      state: WorkerTokenState.INACTIVE,
      description: 'Created by npervic',
    },
    {
      id: '6iMVFfK4VxaiFSdiQHzwQh',
      created_at: '2022-12-13T09:37:43.346139+00:00',
      state: WorkerTokenState.ACTIVE,
      description: 'Created by npervic',
      token: 'M1HCc9JRANwUGUr1ycQzl3hzYUIAt1weT1tVpH6PboNyJXgTCqC7u21pDxPOdA7U',
    },
    {
      id: 'UcbRdkaUbH5z8qFbAnHPe9',
      created_at: '2022-12-13T09:37:42.964505+00:00',
      state: WorkerTokenState.ACTIVE,
      description: 'Created by npervic',
      token: 'BVmZyoWqqxsMmSXZ54dEowJ5hOZEDIpcyLdNPB8ypdB8JW1kdvZRVxqWEFxfDaQO',
    },
    {
      id: 'TpGwe4PacztoB6DBFWx3zB',
      created_at: '2022-12-13T09:37:40.292398+00:00',
      state: WorkerTokenState.ACTIVE,
      description: 'Created by npervic',
      token: 'uVV5UWwuDIPICYnPOmgD5OZbJitYIqTw1UoYvO67Gh2K5dW6PVqG718fIhtiUNBi',
    },
    {
      id: 'N2cniaUF3tro7RobNWuHY9',
      created_at: '2022-12-13T09:37:38.381286+00:00',
      state: WorkerTokenState.ACTIVE,
      description: 'Created by npervic',
      token: '5CSFjXhvSMs6JoNbC1mjXlBa6fR33oPWgQVnYe5sH8DrE0YDIkbPauWUDAxhttlN',
    },
  ],
};

const sortedWorkerTokens = data.tokens.sort((a, b) => a.state.localeCompare(b.state));

export default sortedWorkerTokens;
