/*
Copyright 2023 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';

import { useServiceUnavailableContext } from './service-unavailable-store';
import render from '../../tests/custom-render';

type TestRequestErrorStoreProps = {
  buttonClickValue: boolean;
};

const TestServiceUnavailableStore = ({ buttonClickValue }: TestRequestErrorStoreProps) => {
  const { isServiceUnavailable, setIsServiceUnavailable } = useServiceUnavailableContext();

  return (
    <>
      <button
        data-testid="setFlag"
        aria-label="setFlag"
        onClick={() => setIsServiceUnavailable(buttonClickValue)}
        type="button"
      />
      {!!isServiceUnavailable && <div>Service unavailable</div>}
    </>
  );
};

const renderServiceUnavailableStore = (initState: boolean, buttonClickValue: boolean = false) =>
  render(<TestServiceUnavailableStore buttonClickValue={buttonClickValue} />, {
    providerProps: { serviceUnavailable: { initServiceUnavailableState: initState } },
  });

describe('useServiceUnavailableContext', () => {
  it('should read & set ServiceUnavailable flag', async () => {
    renderServiceUnavailableStore(true);

    expect(screen.getByText('Service unavailable')).toBeInTheDocument();

    const button = screen.queryByTestId('setFlag');

    fireEvent.click(button);

    await waitFor(() => expect(screen.queryByText('Service unavailable')).not.toBeInTheDocument());
  });

  it('should read & set ServiceUnavailable flag #2', async () => {
    renderServiceUnavailableStore(false, true);

    expect(screen.queryByText('Service unavailable')).not.toBeInTheDocument();

    const button = screen.queryByTestId('setFlag');

    fireEvent.click(button);

    await screen.findByText('Service unavailable');
  });
});
