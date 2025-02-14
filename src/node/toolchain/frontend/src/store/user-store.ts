/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { useState } from 'react';
import constate from 'constate';
import { ToolchainUser } from 'common/interfaces/builds-options';

export type UserInitParams = {
  initUser?: ToolchainUser;
};

const useUserStore = ({ initUser = null }: UserInitParams) => {
  const [user, setUserStore] = useState<ToolchainUser | null>(initUser);
  const setUser = (newValues: ToolchainUser | null) => setUserStore(newValues);

  return { user, setUser };
};

export const [UserProvider, useUserContext] = constate(useUserStore);
