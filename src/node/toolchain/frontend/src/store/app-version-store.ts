/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { useState } from 'react';
import constate from 'constate';

export type AppVersionStoreInitProps = {
  initAppVersion?: string | null;
  initServerAppVersion?: string | null;
  initVersionChecking?: boolean;
};

const useAppVersionStore = ({
  initAppVersion = null,
  initServerAppVersion = null,
  initVersionChecking = true,
}: AppVersionStoreInitProps) => {
  const [appVersion, setVersion] = useState<string | null>(initAppVersion);
  const [serverAppVersion, setServerAppVersion] = useState<string | null>(initServerAppVersion);
  const [noAppReload, setNoAppReload] = useState<boolean | undefined>(undefined);
  const setAppVersion = (newValues: string | null) => setVersion(newValues);
  const [versionChecking, setVersionChecking] = useState<boolean>(initVersionChecking);

  return {
    appVersion,
    serverAppVersion,
    setAppVersion,
    setServerAppVersion,
    versionChecking,
    setVersionChecking,
    noAppReload,
    setNoAppReload,
  };
};

export const [AppVersionProvider, useAppVersionContext] = constate(useAppVersionStore);
