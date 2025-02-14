/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen, fireEvent } from '@testing-library/react';

import Targets from './targets';
import render from '../../../tests/custom-render';
import { targets, targetsEmpty, targetsOnlyOneFolder } from '../../../tests/__fixtures__/artifacts/targets';

const renderArtifactTable = (artifact = targets) => render(<Targets artifact={artifact} />);

describe('<Targets />', () => {
  it('should render the component', () => {
    const { asFragment } = renderArtifactTable();

    expect(asFragment()).toMatchSnapshot();
  });

  it('should display 3 files after filtering data', () => {
    renderArtifactTable();

    const textField = screen.getByLabelText('Search file name');

    fireEvent.change(textField, { target: { value: 'file3' } });

    expect(screen.getByText('3 files in total')).toBeInTheDocument();
  });

  it('should display only files if there is no folders in inout data', () => {
    const { asFragment } = renderArtifactTable(targetsOnlyOneFolder);

    expect(asFragment()).toMatchSnapshot();
  });

  it('should display 0 files after filtering data', () => {
    renderArtifactTable();

    const textField = screen.getByLabelText('Search file name');

    fireEvent.change(textField, { target: { value: 'abc' } });

    expect(screen.getByText('0 files in total')).toBeInTheDocument();
  });

  it('should display 0 files if input data is null', () => {
    renderArtifactTable(targetsEmpty);
    expect(screen.getByText('0 files in total')).toBeInTheDocument();
  });

  it('should hide and show subfolders and files when folder name is clicked', () => {
    renderArtifactTable();

    const folderNameLabel = screen.queryByText('folder2/subfolder2a/subfolder2b/');
    const fileNameLabel = screen.queryByText('file300.py');

    expect(folderNameLabel).toBeInTheDocument();
    expect(fileNameLabel).toBeInTheDocument();

    fireEvent.click(folderNameLabel);

    expect(folderNameLabel).toBeInTheDocument();
    expect(fileNameLabel).not.toBeInTheDocument();
  });
});
