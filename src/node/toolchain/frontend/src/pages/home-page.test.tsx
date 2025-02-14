/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen } from '@testing-library/react';

import HomePage from './home-page';
import render from '../../tests/custom-render';

describe('<HomePage />', () => {
  it('should render the component', () => {
    const { asFragment } = render(<HomePage />);

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render welcome text', () => {
    render(<HomePage />);

    expect(screen.getByText('Welcome to Toolchain!')).toBeInTheDocument();
  });
});
