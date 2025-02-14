/*
Copyright 2023 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import render from '../../tests/custom-render';
import ServiceUnavailableSnackbar from './service-unavailable-snackbar';
import queryClient from '../../tests/queryClient';

const renderServiceUnavailableSnackbar = (isServiceUnavailable: boolean = false) => {
  render(
    <QueryClientProvider client={queryClient}>
      <ServiceUnavailableSnackbar />
    </QueryClientProvider>,
    {
      providerProps: {
        serviceUnavailable: {
          initServiceUnavailableState: isServiceUnavailable,
        },
      },
    }
  );
};

describe('<ServiceUnavailableSnackbar />', () => {
  it('should render component', () => {
    renderServiceUnavailableSnackbar(true);

    expect(screen.getByText('Service unavailable at the moment')).toBeInTheDocument();
  });

  it('should not render component', () => {
    renderServiceUnavailableSnackbar();

    expect(screen.queryByText('Service unavailable at the moment')).not.toBeInTheDocument();
  });
});
