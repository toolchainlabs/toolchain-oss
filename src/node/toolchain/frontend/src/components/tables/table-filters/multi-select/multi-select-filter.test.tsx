/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen, fireEvent } from '@testing-library/react';

import MultiSelectFilter from './multi-select-filter';
import render from '../../../../../tests/custom-render';

const defaultFieldValue: string[] = undefined;
const defaultFieldName = 'goals';
const defaultFieldLabel = 'Goals';
const onChangeMock = jest.fn();

const renderMultiSelectFilter = ({
  fieldValue = defaultFieldValue,
  fieldName = defaultFieldName,
  fieldLabel = defaultFieldLabel,
  onChange = onChangeMock,
  options = [],
}: Partial<React.ComponentProps<typeof MultiSelectFilter>> = {}) =>
  render(
    <MultiSelectFilter
      fieldValue={fieldValue}
      fieldName={fieldName}
      onChange={onChange}
      fieldLabel={fieldLabel}
      options={options}
    />
  );

describe('<MultiSelectFilter />', () => {
  it('should render the component', () => {
    const { asFragment } = renderMultiSelectFilter();

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render with default value passed in fieldValue', async () => {
    const props = {
      fieldValue: ['option-1'],
    };

    renderMultiSelectFilter(props);

    expect(screen.getByText('option-1')).toBeInTheDocument();
  });

  it('should render options in list on click', async () => {
    const props = {
      options: ['option-1', 'option-2'],
    };

    renderMultiSelectFilter(props);

    fireEvent.mouseDown(screen.getByRole('combobox'));

    expect(screen.getByRole('listbox'));
    expect(screen.getByText('option-1'));
    expect(screen.getByText('option-2'));
  });

  it('should call onChange if list item is clicked', async () => {
    const props = {
      options: ['option-1', 'option-2'],
    };

    renderMultiSelectFilter(props);

    fireEvent.mouseDown(screen.getByRole('combobox'));
    fireEvent.click(screen.getByText('option-1'));

    expect(onChangeMock).toHaveBeenCalledWith({ [defaultFieldName]: ['option-1'] });
  });

  it('should render empty list item if no options', async () => {
    renderMultiSelectFilter();

    fireEvent.mouseDown(screen.getByRole('combobox'));

    expect(screen.getByRole('listbox'));
    expect(screen.getByText('No options'));
  });
});
