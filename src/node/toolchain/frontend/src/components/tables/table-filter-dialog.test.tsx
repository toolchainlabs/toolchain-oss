/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';

import SelectFilter from 'components/tables/table-filters/select/select-filter';
import { TableFilters } from 'common/interfaces/table';
import TableFilterDialog from './table-filter-dialog';
import RunTimeFilter from './table-filters/run-time/run-time-filter';
import { formatTimeFromSeconds } from 'utils/datetime-formats';
import render from '../../../tests/custom-render';

const updateQuery = jest.fn();
const closeDialog = jest.fn();

const mockFilters: TableFilters = {
  someFilter: {
    name: 'filter1',
    label: 'My Label',
    noFilterValue: undefined,
    fullWidth: false,
    value: 'option1',
    options: ['option1', 'option2', 'option3'],
    filterRender: (value, onChange, name, label, options) => (
      <SelectFilter
        fieldValue={value as string}
        onChange={onChange}
        fieldName={name}
        fieldLabel={label}
        options={options as string[]}
      />
    ),
    chipRender: value => `Since ${value}`,
  },
  runTime: {
    name: 'run_time',
    label: 'Runtime',
    filterRender: (value, onChange, name, label) => (
      <RunTimeFilter fieldValue={value as string[]} onChange={onChange} fieldName={name} fieldLabel={label} />
    ),
    chipRender: values => {
      const [rangeFrom, rangeTo] = values as Array<string | undefined>;
      return `Runtime: ${
        rangeFrom !== undefined
          ? `is longer than ${formatTimeFromSeconds(rangeFrom)}`
          : `is shorter than ${formatTimeFromSeconds(rangeTo)}`
      }`;
    },
    noFilterValue: [undefined, undefined],
    fullWidth: true,
    value: [undefined, undefined],
  },
};

const renderFilterDialog = () =>
  render(<TableFilterDialog isOpen closeDialog={closeDialog} filterList={mockFilters} updateQuery={updateQuery} />);

describe('<TableFilterDialog/>', () => {
  it('should render component', () => {
    const { baseElement } = renderFilterDialog();
    expect(baseElement).toMatchSnapshot();
  });

  it('should reset filter on clear all button', async () => {
    renderFilterDialog();
    expect(screen.queryByLabelText('All')).not.toBeInTheDocument();
    fireEvent.click(screen.queryByText('CLEAR ALL'));

    await waitFor(() => {
      expect(screen.getByLabelText('All')).toBeInTheDocument();
    });
  });

  it('should disable apply button if nothing is changed', async () => {
    renderFilterDialog();
    expect(screen.queryByText('APPLY FILTERS').closest('button')).toBeDisabled();
    fireEvent.click(screen.queryByText('CLEAR ALL'));

    await waitFor(() => {
      expect(screen.queryByText('APPLY FILTERS').closest('button')).not.toBeDisabled();
    });
    fireEvent.mouseDown(screen.getByRole('combobox'));
    fireEvent.click(screen.queryByText('option1'));
    expect(screen.queryByText('APPLY FILTERS').closest('button')).toBeDisabled();
  });

  it('should disable clear button if no filters are aplied', async () => {
    renderFilterDialog();
    expect(screen.queryByText('CLEAR ALL').closest('button')).not.toBeDisabled();
    fireEvent.click(screen.queryByText('CLEAR ALL'));
    expect(screen.queryByText('CLEAR ALL').closest('button')).toBeDisabled();

    fireEvent.mouseDown(screen.getByRole('combobox'));
    fireEvent.click(screen.queryByText('option1'));
    expect(screen.queryByText('CLEAR ALL').closest('button')).not.toBeDisabled();
  });

  it('should not switch runTime filter to ALL while user is moving slider', () => {
    renderFilterDialog();

    // Since element with role of slider is not rendered until it has a value
    const slider = screen.getByDisplayValue('0');
    const sliderRoot = slider.parentElement;

    sliderRoot.getBoundingClientRect = jest.fn(() => ({
      width: 100,
      height: 10,
      bottom: 10,
      left: 0,
      x: 0,
      y: 0,
      right: 0,
      top: 0,
      toJSON: jest.fn(),
    }));

    fireEvent.change(screen.getByDisplayValue('all'), { target: { value: 'runTypeTo' } });

    fireEvent.mouseDown(sliderRoot, { buttons: 1, clientX: 33 });
    fireEvent.mouseUp(sliderRoot, { buttons: 1, clientX: 33 });

    expect(screen.getByText('is shorter than')).toBeInTheDocument();

    fireEvent.mouseDown(sliderRoot, { buttons: 1, clientX: 0 });
    fireEvent.mouseUp(sliderRoot, { buttons: 1, clientX: 0 });

    expect(screen.getByText('is shorter than')).toBeInTheDocument();
  });
});
