/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { useState } from 'react';
import constate from 'constate';

export type OrgAndRepoInitParams = {
  initOrg?: string | null;
  initRepo?: string | null;
};

const useOrgAndRepoStore = ({ initOrg = null, initRepo = null }: OrgAndRepoInitParams) => {
  const [org, setOrgStore] = useState<string | null>(initOrg);
  const [repo, setRepoStore] = useState<string | null>(initRepo);

  const setOrg = (newValues: string) => setOrgStore(newValues);
  const setRepo = (newValues: string) => setRepoStore(newValues);

  return { org, repo, setOrg, setRepo };
};

export const [OrgAndRepoProvider, useOrgAndRepoContext] = constate((props?: OrgAndRepoInitParams) =>
  useOrgAndRepoStore(props)
);
