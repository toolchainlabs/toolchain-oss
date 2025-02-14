/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen, fireEvent } from '@testing-library/react';

import SelectFilter from './select-filter';
import render from '../../../../../tests/custom-render';

const defaultFieldValue: string = undefined;
const defaultFieldName = 'ci';
const defaultFieldLabel = 'Build context';
const onChangeMock = jest.fn();

const renderSelectFilter = ({
  fieldValue = defaultFieldValue,
  fieldName = defaultFieldName,
  fieldLabel = defaultFieldLabel,
  onChange = onChangeMock,
  options = [],
}: Partial<React.ComponentProps<typeof SelectFilter>> = {}) =>
  render(
    <SelectFilter
      fieldValue={fieldValue}
      fieldName={fieldName}
      onChange={onChange}
      fieldLabel={fieldLabel}
      options={options}
    />
  );

describe('<SelectFilter />', () => {
  it('should render the component', () => {
    const props = {
      options: ['option-1', 'option-2'],
    };
    const { asFragment } = renderSelectFilter(props);

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render with default value passed in fieldValue', async () => {
    const props = {
      fieldValue: 'option-1',
      options: ['option-1', 'option-2'],
    };

    renderSelectFilter(props);

    expect(screen.getByRole('combobox')).toHaveTextContent(props.fieldValue);
  });

  it('should render options in list on click', async () => {
    const props = {
      options: ['option-1', 'option-2'],
    };

    renderSelectFilter(props);

    fireEvent.mouseDown(screen.getByRole('combobox'));

    expect(screen.getByRole('listbox'));
    expect(screen.getByText('option-1'));
    expect(screen.getByText('option-2'));
  });

  it('should call onChange if list item is clicked', async () => {
    const props = {
      options: ['option-1', 'option-2'],
    };

    renderSelectFilter(props);

    fireEvent.mouseDown(screen.getByRole('combobox'));
    fireEvent.click(screen.getByText('option-1'));

    expect(onChangeMock).toHaveBeenCalledWith({ [defaultFieldName]: 'option-1' });
  });
});
