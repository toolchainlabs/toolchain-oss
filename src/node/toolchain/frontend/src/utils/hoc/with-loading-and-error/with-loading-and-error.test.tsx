/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import withLoadingAndError from './with-loading-and-error';
import render from '../../../../tests/custom-render';

type TestRenderWithLoadingAndErrorProps = {
  component: any;
  data: any;
  isLoading: boolean;
  errorMessage: string | null;
  props?: any;
};

const TestComponent = ({ name }: { name: string }) => <div>hello {name} from the text component</div>;

const TestRenderWithLoadingAndError = ({
  component,
  data,
  isLoading,
  errorMessage,
  props,
}: TestRenderWithLoadingAndErrorProps) => {
  const Component = withLoadingAndError(component, data, isLoading, errorMessage);

  // eslint-disable-next-line react/jsx-props-no-spreading
  return <Component {...props} />;
};

describe('withLoadingAndError', () => {
  it('should render loader', () => {
    const { asFragment } = render(
      <TestRenderWithLoadingAndError
        component={TestComponent}
        data={null}
        isLoading={true}
        errorMessage={null}
        props={{ name: 'Jerry' }}
      />
    );

    expect(asFragment()).toMatchSnapshot();
  });

  it('should show error', async () => {
    const { asFragment } = render(
      <TestRenderWithLoadingAndError
        component={TestComponent}
        data={null}
        isLoading={false}
        errorMessage="Error making request"
        props={{ name: 'Jerry' }}
      />,
      { providerProps: { requestError: { initErrorMessage: 'Error making request' } } }
    );

    await screen.findByText('Error making request');

    expect(asFragment()).toMatchSnapshot();
  });

  it('should close error message on click', async () => {
    const user = userEvent.setup();
    render(
      <TestRenderWithLoadingAndError
        component={TestComponent}
        data={null}
        isLoading={false}
        errorMessage="Error making request"
        props={{ name: 'Jerry' }}
      />,
      { providerProps: { requestError: { initErrorMessage: 'Error making request' } } }
    );

    const errorModal = await screen.findByRole('alert');

    expect(errorModal).toBeInTheDocument();

    user.click(document.body);

    await waitFor(() => {
      expect(screen.queryByRole('alert')).toBeNull();
    });
  });

  it('should render component with prop', async () => {
    render(
      <TestRenderWithLoadingAndError
        component={TestComponent}
        data={[1, 2, 3]}
        isLoading={false}
        errorMessage={null}
        props={{ name: 'Jerry' }}
      />
    );

    expect(screen.getByText(/Jerry/)).toBeInTheDocument();
  });
});
