/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { fireEvent, screen } from '@testing-library/react';

import TableSortDialog from './table-sort-dialog-mobile';
import render from '../../../tests/custom-render';

type TableProps = {
  order: 'asc' | 'desc';
  orderBy: string | null;
};

const updateQueryMock = jest.fn();

const mockColumns: Array<{ label: string; sortName: string }> = [
  { label: 'Column 1 label', sortName: 'column1' },
  { label: 'Column 2 label', sortName: 'column2' },
];

const renderTableSortDialog = (
  { sort }: { sort: TableProps } = {
    sort: {
      order: 'asc',
      orderBy: null,
    },
  }
) =>
  render(
    <TableSortDialog isOpen closeDialog={() => {}} columns={mockColumns} sort={sort} updateQuery={updateQueryMock} />
  );

describe('<TableSortDialog />', () => {
  it('should render component', () => {
    const { baseElement } = renderTableSortDialog();

    expect(baseElement).toMatchSnapshot();
  });

  it('should have disabled apply and clear buttons on default state', () => {
    renderTableSortDialog();

    expect(screen.getByRole('button', { name: 'Apply sorting' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Reset to default' })).toBeDisabled();
  });

  it('should call updateQueryMock on save', () => {
    renderTableSortDialog();

    fireEvent.change(screen.getByDisplayValue('Default').closest('select'), {
      target: { value: JSON.stringify({ order: 'asc', orderBy: 'column2' }) },
    });

    expect(screen.getByRole('button', { name: 'Apply sorting' })).not.toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Apply sorting' }));

    expect(updateQueryMock).toBeCalledWith('update', { sort: 'column2' });
  });

  it('should call updateQueryMock on save #2', () => {
    renderTableSortDialog();

    fireEvent.change(screen.getByDisplayValue('Default').closest('select'), {
      target: { value: JSON.stringify({ order: 'desc', orderBy: 'column2' }) },
    });

    expect(screen.getByRole('button', { name: 'Apply sorting' })).not.toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Apply sorting' }));

    expect(updateQueryMock).toBeCalledWith('update', { sort: '-column2' });
  });

  it('should call updateQueryMock for default state', () => {
    renderTableSortDialog({ sort: { order: 'asc', orderBy: 'column1' } });

    fireEvent.change(screen.getByDisplayValue(/Column 1 label/).closest('select'), {
      target: { value: JSON.stringify({ order: 'asc', orderBy: null }) },
    });

    expect(screen.getByRole('button', { name: 'Apply sorting' })).not.toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Apply sorting' }));

    expect(updateQueryMock).toBeCalledWith('update', { sort: undefined });
  });

  it('should reset local state on reset button', () => {
    renderTableSortDialog();

    fireEvent.change(screen.getByDisplayValue('Default').closest('select'), {
      target: { value: JSON.stringify({ order: 'asc', orderBy: 'column2' }) },
    });

    expect(screen.getByRole('button', { name: 'Reset to default' })).not.toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Reset to default' }));

    expect(screen.getByRole('button', { name: 'Reset to default' })).toBeDisabled();
  });

  it('should enable and disable apply button on select change', () => {
    renderTableSortDialog({ sort: { order: 'asc', orderBy: 'column1' } });

    expect(screen.getByRole('button', { name: 'Apply sorting' })).toBeDisabled();

    fireEvent.change(screen.getByDisplayValue(/Column 1 label/).closest('select'), {
      target: { value: JSON.stringify({ order: 'asc', orderBy: 'column2' }) },
    });

    expect(screen.getByRole('button', { name: 'Apply sorting' })).not.toBeDisabled();

    fireEvent.change(screen.getByDisplayValue(/Column 2 label/).closest('select'), {
      target: { value: JSON.stringify({ order: 'asc', orderBy: 'column1' }) },
    });

    expect(screen.getByRole('button', { name: 'Apply sorting' })).toBeDisabled();
  });
});
