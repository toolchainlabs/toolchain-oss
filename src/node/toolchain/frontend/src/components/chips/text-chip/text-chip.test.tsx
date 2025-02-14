/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';

import TextChip from './text-chip';
import render from '../../../../tests/custom-render';

const renderTextChip = ({ text }: Partial<React.ComponentProps<typeof TextChip>> = {}) =>
  render(<TextChip text={text} />);

describe('<TextChip />', () => {
  it('should render passed text', () => {
    const { asFragment } = renderTextChip({ text: 'typecheck' });

    expect(asFragment()).toMatchSnapshot();
  });
});
