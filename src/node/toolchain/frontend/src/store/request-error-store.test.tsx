/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen, fireEvent } from '@testing-library/react';

import { RequestErrorProvider, useRequestErrorContext } from './request-error-store';
import render from '../../tests/custom-render';

type TestRequestErrorStoreProps = {
  errorValue: string;
};

const TestRequestErrorStore = ({ errorValue }: TestRequestErrorStoreProps) => {
  const { errorMessage, setErrorMessage } = useRequestErrorContext();

  return (
    <>
      <button
        data-testid="setErrorButton"
        aria-label="setError"
        onClick={() => setErrorMessage(errorValue)}
        type="button"
      />
      {errorMessage && <div data-testid="error">{errorMessage}</div>}
    </>
  );
};

const renderRequestErrorStore = (errorValue: string, initError?: string) =>
  render(
    <RequestErrorProvider initErrorMessage={initError}>
      <TestRequestErrorStore errorValue={errorValue} />
    </RequestErrorProvider>,
    { providerProps: { requestError: { initErrorMessage: initError } } }
  );

describe('useRequestErrorStore', () => {
  it('should not render error default', () => {
    renderRequestErrorStore('Set error value');

    expect(screen.queryByTestId('error')).not.toBeInTheDocument();
  });

  it('should render error from init store value', () => {
    renderRequestErrorStore('Set error value', 'Init error value');

    expect(screen.getByTestId('error')).toBeInTheDocument();
    expect(screen.getByText('Init error value')).toBeInTheDocument();
  });

  it('should render error from button click', async () => {
    renderRequestErrorStore('Set error value');

    const button = screen.queryByTestId('setErrorButton');

    fireEvent.click(button);

    await screen.findByTestId('error');
    await screen.findByText('Set error value');
  });
});
