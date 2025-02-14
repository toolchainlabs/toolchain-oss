/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { ToolchainUser } from 'common/interfaces/builds-options';

const users: ToolchainUser[] = [
  {
    api_id: 'QA7ObWyoky5xBMqbBN1g',
    username: 'user1',
    full_name: 'John Doe',
    avatar_url: 'https://example.com/avatar-user1',
  },
  {
    api_id: 'iFxUggn8e4Eu12KYOOR3',
    username: 'user2',
    full_name: 'Jane Doe',
    avatar_url: null,
  },
  {
    api_id: 'bbNlh6cA8YHYjD5VFvKk',
    username: 'user3',
    full_name: 'Peter Doe',
    avatar_url: 'https://example.com/avatar-user3',
  },
];

export default users;
