/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { fireEvent, screen } from '@testing-library/react';

import TextBlock from './text-block';
import render from '../../../tests/custom-render';

const textElementSmall = (
  <span>
    Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis
    quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo
  </span>
);

const renderTextBlock = ({ children, showExpand }: Partial<React.ComponentProps<typeof TextBlock>> = {}) =>
  render(<TextBlock showExpand={showExpand}>{children}</TextBlock>);

describe('<TextBlock />', () => {
  it('should render text block with no expanded', () => {
    renderTextBlock({ children: textElementSmall, showExpand: false });

    expect(screen.queryByLabelText(/expand text/i)).not.toBeInTheDocument();
  });

  it('should render text block with expanded', () => {
    renderTextBlock({ children: textElementSmall, showExpand: true });

    expect(screen.getByLabelText(/expand text/i)).toBeInTheDocument();
  });

  it('should toggle colapsed state on click', () => {
    renderTextBlock({ children: textElementSmall, showExpand: true });

    expect(screen.getByLabelText(/expand text/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/collapse text/i)).not.toBeInTheDocument();

    fireEvent.click(screen.queryByLabelText(/expand text/i));

    expect(screen.queryByLabelText(/expand text/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/collapse text/i)).toBeInTheDocument();

    fireEvent.click(screen.queryByLabelText(/collapse text/i));

    expect(screen.getByLabelText(/expand text/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/collapse text/i)).not.toBeInTheDocument();
  });
});
