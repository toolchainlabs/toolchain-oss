/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { fireEvent, screen } from '@testing-library/react';

import CodeBlock from './codeblock';
import render from '../../../tests/custom-render';

const command =
  'pants --pants-bin-name=./pants --pants-version=2.3.0.dev3 --no-dynamic-ui typecheck src/python/toolchain/aws/::';
const writeTextMock = jest.fn();

// Declare the writeText method since in jsdom its undefined (https://stackoverflow.com/a/62356286/14436058)
Object.assign(navigator, {
  clipboard: {
    writeText: () => {},
  },
});
jest.spyOn(navigator.clipboard, 'writeText').mockImplementation(writeTextMock);

const renderCodeBlock = ({
  children = command,
  convertAnsi = false,
}: Partial<React.ComponentProps<typeof CodeBlock>> = {}) =>
  render(<CodeBlock convertAnsi={convertAnsi}>{children}</CodeBlock>);

describe('<CodeBlock />', () => {
  afterAll(() => jest.clearAllMocks());

  it('should render the component', () => {
    const { asFragment } = renderCodeBlock();

    expect(asFragment()).toMatchSnapshot();
  });

  it('should show writeTextMock on command copy', async () => {
    renderCodeBlock();

    fireEvent.click(screen.queryByLabelText('Copy text'));

    expect(writeTextMock).toHaveBeenCalledWith(command);
  });

  it('should call snackbar on command copy', async () => {
    const { asFragment } = renderCodeBlock();

    fireEvent.click(screen.queryByLabelText('Copy text'));

    expect(screen.getByText('Copied')).toBeInTheDocument();
    expect(asFragment()).toMatchSnapshot();
  });

  it('should convert ANSI text if the option is specified', async () => {
    const { asFragment } = renderCodeBlock({ children: '\u001b[34mhello world', convertAnsi: true });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should show contracted version if length > 300 is provided', async () => {
    const text =
      'Lorem, ipsum dolor sit amet consectetur adipisicing elit.  us saepe ut amet expedita in, neque assumenda umenda hic dolor numquam placeat! Atque quasi nobis eveniet minima odit possimus repellendus fugiat error nesciunt nam quo nisi eligendi quibusdam facere, quibusdam facere quibusdam facere quibusdam facere ';
    renderCodeBlock({ children: text });

    expect(screen.getByLabelText('Expand text')).toBeInTheDocument();
    expect(screen.queryByLabelText('Collapse text')).not.toBeInTheDocument();

    fireEvent.click(screen.queryByLabelText('Expand text'));

    expect(screen.queryByLabelText('Expand text')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Collapse text')).toBeInTheDocument();
  });
});
