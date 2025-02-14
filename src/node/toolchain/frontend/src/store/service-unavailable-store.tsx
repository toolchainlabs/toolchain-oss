/*
Copyright 2023 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { useState } from 'react';
import constate from 'constate';

export type ServiceUnavailableParams = {
  initServiceUnavailableState?: boolean;
};

const useServiceUnavailableStore = ({ initServiceUnavailableState = false }: ServiceUnavailableParams) => {
  const [isServiceUnavailable, setIsServiceUnavailable] = useState<boolean>(initServiceUnavailableState);

  return {
    isServiceUnavailable,
    setIsServiceUnavailable,
  };
};

export const [ServiceUnavailableProvider, useServiceUnavailableContext] = constate((props?: ServiceUnavailableParams) =>
  useServiceUnavailableStore(props)
);
