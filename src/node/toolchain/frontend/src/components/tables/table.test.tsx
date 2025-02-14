/*
Copyright 2019 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { fireEvent, screen, waitFor } from '@testing-library/react';

import { TableColumns, TableFilters } from 'common/interfaces/table';
import Table, { TableProps } from 'components/tables/table';
import SelectFilter from './table-filters/select/select-filter';
import buildList from '../../../tests/__fixtures__/builds-list';
import render from '../../../tests/custom-render';

type Data = { started: string; duration: number; outcome: string };

const handleTableQueryChange = jest.fn();
const refreshTableData = jest.fn();
const rowClick = jest.fn();
const openNewTabClick = jest.fn();
const handleFetchNext = jest.fn();

const tableName = 'builds';
const tableColumns: TableColumns<Data> = {
  started: {
    sortable: true,
    sortName: 'started',
    label: 'STARTED',
    renderValue: ({ started }) => <>{started}</>,
  },
  duration: {
    sortable: true,
    sortName: 'run_time',
    label: 'DURATION',
    renderValue: ({ duration }) => <>{duration}</>,
  },
  outcome: {
    sortable: false,
    sortName: null,
    label: 'OUTCOME',
    renderValue: ({ outcome }) => <>{outcome}</>,
  },
};
const tableData: { [key: string]: Data | string }[] = [
  {
    id: '1',
    started: { started: 'time started first', duration: 111, outcome: 'Success' },
    duration: { started: 'time started first', duration: 111, outcome: 'Success' },
    outcome: { started: 'time started first', duration: 111, outcome: 'Success' },
  },
  {
    id: '2',
    started: { started: 'time started second', duration: 222, outcome: 'Aborted' },
    duration: { started: 'time started second', duration: 222, outcome: 'Aborted' },
    outcome: { started: 'time started second', duration: 222, outcome: 'Aborted' },
  },
  {
    id: '3',
    started: { started: 'time started third', duration: 333, outcome: 'Failed' },
    duration: { started: 'time started third', duration: 333, outcome: 'Failed' },
    outcome: { started: 'time started third', duration: 333, outcome: 'Failed' },
  },
  {
    id: '4',
    started: { started: 'time started fourth', duration: 444, outcome: 'Not available' },
    duration: { started: 'time started fourth', duration: 444, outcome: 'Not available' },
    outcome: { started: 'time started fourth', duration: 444, outcome: 'Not available' },
  },
  {
    id: ' 5',
    started: { started: 'time started fifth', duration: 555, outcome: 'Success' },
    duration: { started: 'time started fifth', duration: 555, outcome: 'Success' },
    outcome: { started: 'time started fifth', duration: 555, outcome: 'Success' },
  },
];
const tableFilters: TableFilters = {
  started: {
    name: 'started',
    label: 'Started',
    options: ['first', 'second', 'third'],
    noFilterValue: undefined,
    fullWidth: false,
    value: undefined,
    filterRender: (value, onChange, name, label, options) => (
      <SelectFilter
        fieldValue={value as string}
        onChange={onChange}
        fieldName={name}
        fieldLabel={label}
        options={options}
      />
    ),
    chipRender: values => `Started: ${values}`,
  },
};
const sortObj: { order: 'asc' | 'desc'; orderBy: string } = { order: 'asc', orderBy: null };
const cacheIndicators = buildList[13].indicators;

const renderTable = ({
  columns = tableColumns,
  filters = tableFilters,
  data = tableData,
  sort = sortObj,
  isLoading = false,
  refreshData = refreshTableData,
  onQueryChange = handleTableQueryChange,
  onRowClick = rowClick,
  onOpenNewTabClick = openNewTabClick,
  fetchNext = handleFetchNext,
  isLoadingNext = false,
  isLastPage = false,
  name = tableName,
  indicators = null,
  maxPaginationReached,
}: Partial<TableProps<Data>> = {}) =>
  render(
    <Routes>
      <Route
        path="/"
        element={
          <Table
            name={name}
            onRowClick={onRowClick}
            onOpenNewTabClick={onOpenNewTabClick}
            sort={sort}
            data={data}
            columns={columns}
            filters={filters}
            isLoading={isLoading}
            refreshData={refreshData}
            onQueryChange={onQueryChange}
            fetchNext={fetchNext}
            isLoadingNext={isLoadingNext}
            isLastPage={isLastPage}
            indicators={indicators}
            maxPaginationReached={maxPaginationReached}
          />
        }
      />
    </Routes>,
    { wrapperProps: { pathname: '/' } }
  );

describe('<Table />', () => {
  beforeEach(() => {
    // Define window.scrollTo method since jest dosent support it
    const noop = () => {};
    Object.defineProperty(window, 'scrollTo', { value: noop, writable: true });
  });

  afterEach(() => {
    handleTableQueryChange.mockReset();
    refreshTableData.mockReset();
    rowClick.mockReset();
  });

  afterAll(() => {
    // Clean up window.scrollTo definition
    delete window.scrollTo;
    jest.clearAllMocks();
  });

  it('should render loader', () => {
    renderTable({ isLoading: true });

    expect(screen.getByText(`Loading ${tableName}...`)).toBeInTheDocument();
  });

  it('should render provided header and rows', () => {
    const { container } = renderTable();

    container.querySelector('thead td').childNodes.forEach((col, index) => {
      expect(col.textContent).toContain(tableColumns[Object.keys(tableColumns)[index]].label);
    });

    [...container.querySelectorAll('tbody tr')]
      .filter(element => element.className.includes('tableRowSpacer'))
      .forEach((row, rowIndex) => {
        if (!row.className.includes('tableRowSpacer')) {
          row.childNodes.forEach((cell, cellIndex) => {
            expect(cell.textContent).toContain(
              (tableData[rowIndex][Object.keys(tableData[rowIndex])[cellIndex]] as any)[
                Object.keys(tableColumns)[cellIndex]
              ]
            );
          });
        }
      });
  });

  it('should open filer dialog click', async () => {
    renderTable();

    fireEvent.click(screen.getByLabelText('show filters'));

    expect(screen.getByText('Filters')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('close filters'));

    await waitFor(() => expect(screen.queryByText('Filters')).not.toBeInTheDocument());
  });

  it('should apply filters on button click', async () => {
    renderTable();

    fireEvent.click(screen.getByLabelText('show filters'));
    await screen.findByText('Filters');

    const select = screen.getByRole('combobox');

    fireEvent.mouseDown(select);

    fireEvent.click(screen.getByText(tableFilters.started.options[1]));

    await screen.findByDisplayValue(tableFilters.started.options[1]);

    fireEvent.click(screen.getByText('APPLY FILTERS'));

    expect(handleTableQueryChange).toHaveBeenCalledWith('update', { started: tableFilters.started.options[1] });
    expect(handleTableQueryChange).toHaveBeenCalledTimes(1);
  });

  it('should empty filter on empty option', async () => {
    const value = 'first';
    renderTable({ filters: { started: { ...tableFilters.started, value } } });

    fireEvent.click(screen.getByLabelText('show filters'));
    await screen.findByText('Filters');

    const select = screen.getByRole('combobox');

    fireEvent.mouseDown(select);

    fireEvent.click(screen.getByText('All'));

    await screen.findByText('All');

    fireEvent.click(screen.getByText('APPLY FILTERS'));

    expect(handleTableQueryChange).toHaveBeenCalledWith('update', { started: undefined });
    expect(handleTableQueryChange).toHaveBeenCalledTimes(1);
  });

  it('should remove selected filter on click', async () => {
    const value = 'first';
    renderTable({ filters: { started: { ...tableFilters.started, value } } });

    expect(screen.getByText(tableFilters.started.chipRender(value))).toBeInTheDocument();

    fireEvent.click(
      screen.queryByText(tableFilters.started.chipRender(value)).parentElement.parentElement.childNodes[1]
    );

    expect(handleTableQueryChange).toHaveBeenCalledWith('update', { col1: undefined });
    expect(handleTableQueryChange).toHaveBeenCalledTimes(1);
  });

  it('should reset filters on clear all chip', async () => {
    const value = 'first';
    renderTable({ filters: { started: { ...tableFilters.started, value } } });

    fireEvent.click(screen.getByText('clear all'));

    expect(handleTableQueryChange).toHaveBeenCalledWith('reset');
    expect(handleTableQueryChange).toHaveBeenCalledTimes(1);
  });

  it('should keep dialog open after clearing filters', async () => {
    renderTable();

    fireEvent.click(screen.getByLabelText('show filters'));
    await screen.findByText('Filters');

    fireEvent.click(screen.getByText('CLEAR ALL'));

    await screen.findByText('Filters');
  });

  it('should sort on asc on click', () => {
    renderTable();

    fireEvent.click(screen.getByText('STARTED'));

    expect(handleTableQueryChange).toHaveBeenCalledWith('update', { sort: 'started' });
    expect(handleTableQueryChange).toHaveBeenCalledTimes(1);
  });

  it('should sort desc on click', () => {
    renderTable({ sort: { order: 'asc', orderBy: 'started' } });

    fireEvent.click(screen.getByText('STARTED'));

    expect(handleTableQueryChange).toHaveBeenCalledWith('update', { sort: '-started' });
    expect(handleTableQueryChange).toHaveBeenCalledTimes(1);
  });

  it('should refresh data on click', () => {
    renderTable();

    fireEvent.click(screen.getByLabelText('refresh'));

    expect(refreshTableData).toHaveBeenCalled();
  });

  it('should render disabled refresh button if isLoading is true', () => {
    renderTable({ isLoading: true });

    expect(screen.getByLabelText('refresh').closest('button')).toHaveAttribute('disabled');
  });

  it('should render loading message with name if loading next page', () => {
    renderTable({ isLoadingNext: true });

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('should display all data loaded message', () => {
    renderTable({ isLastPage: true });

    expect(screen.getByText(`All ${tableName} are loaded`)).toBeInTheDocument();
  });

  it('should call scrollTo on back to top button click', () => {
    const scrollToSpy = jest.spyOn(window, 'scrollTo');

    renderTable({ isLastPage: true });

    fireEvent.click(screen.getByText(/back to top/i));

    expect(scrollToSpy).toHaveBeenCalled();
    expect(scrollToSpy).toHaveBeenCalledWith({
      top: 0,
      behavior: 'smooth',
    });
  });

  it('should call fetchNextMock on load more click', () => {
    renderTable();

    fireEvent.click(screen.getByText(/load more/i));

    expect(handleFetchNext).toHaveBeenCalled();
  });

  it('should call openNewTabClick on open new tab click', () => {
    renderTable();

    fireEvent.click(screen.getAllByText(/open new tab/i)[0]);

    expect(openNewTabClick).toHaveBeenCalled();
  });

  it('should not render pagination', () => {
    renderTable({ fetchNext: null });

    expect(screen.queryByText(/load more/i)).not.toBeInTheDocument();
  });

  it('should render default no data message', () => {
    renderTable({ data: [] });

    expect(screen.getByText(`No ${tableName} found`)).toBeInTheDocument();
  });

  it('should not render open in new tab', () => {
    renderTable({ onOpenNewTabClick: null });

    expect(screen.queryByText(/open new tab/i)).not.toBeInTheDocument();
  });

  it('should call onRowClick', () => {
    renderTable();

    fireEvent.click(screen.queryByText(/time started first/i));

    expect(rowClick).toHaveBeenCalled();
  });

  it('should not call onRowClick', () => {
    renderTable({ onRowClick: null });

    fireEvent.click(screen.queryByText(/time started first/i));

    expect(rowClick).not.toHaveBeenCalled();
  });

  it('should not render time saved indicators', () => {
    renderTable({ indicators: cacheIndicators });

    expect(screen.queryByText('2 minutes saved')).not.toBeInTheDocument();
  });

  it('should render cache hit rate indicators', () => {
    renderTable({ indicators: cacheIndicators });

    expect(screen.getByText('50% from cache')).toBeInTheDocument();
  });

  it('should not render any indicators', () => {
    renderTable();

    expect(screen.queryByText('50% from cache')).not.toBeInTheDocument();
  });

  it('should render maximum page number reached', () => {
    renderTable({ maxPaginationReached: true, isLastPage: true });

    expect(screen.getByText('Maximum page number reached')).toBeInTheDocument();
  });

  it('should not break app when unknown sort argument used', () => {
    const { container } = renderTable({ sort: { order: 'asc', orderBy: 'randommmm' } });

    container.querySelector('thead td').childNodes.forEach((col, index) => {
      expect(col.textContent).toContain(tableColumns[Object.keys(tableColumns)[index]].label);
    });

    [...container.querySelectorAll('tbody tr')]
      .filter(element => element.className.includes('tableRowSpacer'))
      .forEach((row, rowIndex) => {
        if (!row.className.includes('tableRowSpacer')) {
          row.childNodes.forEach((cell, cellIndex) => {
            expect(cell.textContent).toContain(
              (tableData[rowIndex][Object.keys(tableData[rowIndex])[cellIndex]] as any)[
                Object.keys(tableColumns)[cellIndex]
              ]
            );
          });
        }
      });
  });
});
