/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

type TabFilter = { label: string; value: { [key: string]: string | number }; noDataText: string };
export type TableSort = { order: 'asc' | 'desc' | null; orderBy: string | null };
export type TableData<T> = { [key: string]: T | string }[];
type Column<T> = {
  sortable: boolean;
  sortName: string;
  label: string;
  renderValue: (data: T) => JSX.Element;
  width?: number;
};
export type FormFieldValue = { [key: string]: string | string[] | undefined };
type RenderFilter = (
  value: string | string[] | number,
  onChange: (formField: FormFieldValue) => void,
  name: string,
  label: string,
  options?: any[]
) => JSX.Element;
type ChipRender = (value: string | string[] | number | number[]) => string;

type Filter = {
  name: string;
  label: string;
  fullWidth: boolean;
  value: string[] | string | number | number[];
  noFilterValue: undefined | [undefined, undefined];
  options?: any[];
  filterRender: RenderFilter;
  chipRender: ChipRender;
};

export type TableFilters = {
  [key: string]: Filter;
};

export type TableTabFilters = {
  [key: string]: TabFilter;
};

export type TableColumns<T> = {
  [key: string]: Column<T>;
};
