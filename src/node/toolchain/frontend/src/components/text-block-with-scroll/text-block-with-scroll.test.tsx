/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';

import TextBlockWithScroll from './text-block-with-scroll';
import render from '../../../tests/custom-render';

const textElement = (
  <span>
    Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis
    quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo
  </span>
);

const renderTextBlockWithScroll = ({
  children,
  size = 'small',
  color = 'gray',
}: Partial<React.ComponentProps<typeof TextBlockWithScroll>> = {}) =>
  render(
    <TextBlockWithScroll size={size} color={color}>
      {children}
    </TextBlockWithScroll>
  );

describe('<TextBlockWithScroll />', () => {
  it('should render text block size small and color blue', () => {
    const { asFragment } = renderTextBlockWithScroll({ children: textElement, size: 'small', color: 'blue' });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render text block size large and color gray', () => {
    const { asFragment } = renderTextBlockWithScroll({ children: textElement, size: 'large', color: 'gray' });

    expect(asFragment()).toMatchSnapshot();
  });
});
