/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { useState } from 'react';
import constate from 'constate';

export type RequestErrorParams = {
  initErrorMessage?: string;
};

const useRequestErrorStore = ({ initErrorMessage = null }: RequestErrorParams) => {
  const [errorMessage, setErrorMessage] = useState<string | null>(initErrorMessage);

  return { errorMessage, setErrorMessage };
};

export const [RequestErrorProvider, useRequestErrorContext] = constate((props?: RequestErrorParams) =>
  useRequestErrorStore(props)
);
