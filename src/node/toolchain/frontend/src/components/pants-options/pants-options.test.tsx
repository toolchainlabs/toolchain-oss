/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen, fireEvent } from '@testing-library/react';

import PantsOptions from './pants-options';
import render from '../../../tests/custom-render';
import { pantsOptionsEmpty, pantsOptions } from '../../../tests/__fixtures__/artifacts/pants-options';

const writeTextMock = jest.fn();

const renderPantsOptions = (artifact = pantsOptions) => render(<PantsOptions artifact={artifact} />);

Object.assign(navigator, {
  clipboard: {
    writeText: () => {},
  },
});

jest.spyOn(navigator.clipboard, 'writeText').mockImplementation(writeTextMock);

describe('<PantsOptions>', () => {
  it('should render the component', () => {
    const { asFragment } = renderPantsOptions();

    expect(asFragment()).toMatchSnapshot();
  });

  it('should open and close array presentation', () => {
    renderPantsOptions();

    expect(screen.queryByText(/toolchain.pants.internal/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByText(/backend_packages/));

    expect(screen.getByText(/toolchain.pants.internal/)).toBeInTheDocument();
  });

  it('should open and close object presentation', () => {
    renderPantsOptions();

    expect(screen.getByText(/backend_packages/)).toBeInTheDocument();

    fireEvent.click(screen.getByText(/GLOBAL/));

    expect(screen.queryByText(/backend_packages/)).not.toBeInTheDocument();
  });

  it('should display filtered data after searching for a string', () => {
    renderPantsOptions();

    const textField = screen.getByLabelText('Search options');

    fireEvent.change(textField, { target: { value: 'tool' } });

    expect(screen.getByText(/backend_packages/)).toBeInTheDocument();
    expect(screen.queryByText(/auth/)).not.toBeInTheDocument();
  });

  it('should display filtered data after searching for a number', () => {
    renderPantsOptions();

    const textField = screen.getByLabelText('Search options');

    fireEvent.change(textField, { target: { value: '6' } });

    expect(screen.getByText(/local_store_shard_count/)).toBeInTheDocument();
    expect(screen.queryByText(/auth/)).not.toBeInTheDocument();
  });

  it('should display filtered data after searching for a boolean', () => {
    renderPantsOptions();

    const textField = screen.getByLabelText('Search options');

    fireEvent.change(textField, { target: { value: 'true' } });

    expect(screen.getByText(/colors/)).toBeInTheDocument();
    expect(screen.queryByText(/auth/)).not.toBeInTheDocument();
  });

  it('should display filtered data after searching for a null', () => {
    renderPantsOptions();

    const textField = screen.getByLabelText('Search options');

    fireEvent.change(textField, { target: { value: 'null' } });

    expect(screen.getByText(/org/)).toBeInTheDocument();
    expect(screen.queryByText(/GLOBAL/)).not.toBeInTheDocument();
  });

  it('should display filtered data after searching for an object', () => {
    renderPantsOptions();

    const textField = screen.getByLabelText('Search options');

    fireEvent.change(textField, { target: { value: '{' } });

    expect(screen.getByText(/log_levels_by_target/)).toBeInTheDocument();
    expect(screen.queryByText(/auth/)).not.toBeInTheDocument();
  });

  it('should display filtered data after searching for a object key', () => {
    renderPantsOptions();

    const textField = screen.getByLabelText('Search options');

    fireEvent.change(textField, { target: { value: 'back' } });

    expect(screen.getByText(/GLOBAL/)).toBeInTheDocument();
    expect(screen.queryByText(/colors/)).not.toBeInTheDocument();
    expect(screen.queryByText(/auth/)).not.toBeInTheDocument();
  });

  it('should clear search succesfully', () => {
    renderPantsOptions();

    expect(screen.getByText(/GLOBAL/)).toBeInTheDocument();
    expect(screen.getByText(/auth_file/)).toBeInTheDocument();

    const textField = screen.getByLabelText('Search options');

    fireEvent.change(textField, { target: { value: 'ddd' } });

    expect(screen.queryByText(/GLOBAL/)).not.toBeInTheDocument();
    expect(screen.queryByText(/auth_file/)).not.toBeInTheDocument();

    fireEvent.change(textField, { target: { value: '' } });

    expect(screen.getByText(/GLOBAL/)).toBeInTheDocument();
    expect(screen.getByText(/auth_file/)).toBeInTheDocument();
  });

  it('should display 0 files if input data is null', () => {
    renderPantsOptions(pantsOptionsEmpty);

    expect(screen.queryByText(/GLOBAL/)).not.toBeInTheDocument();
    expect(screen.queryByText(/auth/)).not.toBeInTheDocument();
  });

  it('should display 0 files if nothing match the search input', () => {
    renderPantsOptions();

    const textField = screen.getByLabelText('Search options');
    fireEvent.change(textField, { target: { value: 'no_match' } });

    expect(screen.queryByText(/GLOBAL/)).not.toBeInTheDocument();
    expect(screen.queryByText(/auth/)).not.toBeInTheDocument();
  });

  it('should copy string value to clipboard', () => {
    renderPantsOptions();

    fireEvent.click(screen.getByText(/backend_packages/));

    fireEvent.mouseEnter(screen.getByText(/toolchain.pants.internal/));

    fireEvent.click(screen.getByText('Copy'));

    expect(writeTextMock).toBeCalledWith('toolchain.pants.internal');
  });

  it('should copy number value to clipboard', () => {
    renderPantsOptions();

    fireEvent.mouseEnter(screen.getByText(/6/));

    fireEvent.click(screen.getByText('Copy'));

    expect(writeTextMock).toBeCalledWith(16);
  });

  it('should copy boolean value to clipboard', () => {
    renderPantsOptions();

    fireEvent.mouseEnter(screen.getByText(/true/));

    fireEvent.click(screen.getByText('Copy'));

    expect(writeTextMock).toBeCalledWith(true);
  });

  it('should copy null value to clipboard', () => {
    renderPantsOptions();

    fireEvent.mouseEnter(screen.getByText(/null/));

    fireEvent.click(screen.getByText('Copy'));

    expect(writeTextMock).toBeCalledWith('null');
  });

  it('should copy object value to clipboard', () => {
    renderPantsOptions();

    fireEvent.mouseEnter(screen.getByText(/{/));

    fireEvent.click(screen.getByText('Copy'));

    expect(writeTextMock).toBeCalledWith('{}');
  });

  it('should copy big object value to clipboard', () => {
    renderPantsOptions();

    fireEvent.mouseEnter(screen.getAllByText('2 items')[0]);

    fireEvent.click(screen.getByText('Copy'));

    expect(writeTextMock).toBeCalledWith(JSON.stringify(pantsOptions.content));
  });
});
