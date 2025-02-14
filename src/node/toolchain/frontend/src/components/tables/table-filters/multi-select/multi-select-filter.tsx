/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import Checkbox from '@mui/material/Checkbox';
import Input from '@mui/material/Input';
import ListItemText from '@mui/material/ListItemText';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import InputLabel from '@mui/material/InputLabel';

type MultiSelectFilterProps = {
  fieldValue: string[];
  onChange: (formField: { [key: string]: string | string[] }) => void;
  fieldName: string;
  fieldLabel: string;
  options: string[];
};

const MultiSelectFilter = ({
  fieldValue = [],
  onChange,
  fieldName,
  fieldLabel,
  options = [],
}: MultiSelectFilterProps) => (
  <>
    <InputLabel id={fieldName}>{fieldLabel}</InputLabel>
    <Select
      labelId={fieldName}
      id={`select-${fieldName}`}
      label={fieldLabel}
      value={fieldValue}
      multiple
      fullWidth
      color="primary"
      input={<Input />}
      renderValue={(value: string[]) => value && (value as string[]).join(', ')}
      onChange={event => {
        const value = event.target.value as string[];

        onChange({ [fieldName]: value });
      }}
      SelectDisplayProps={{
        role: 'combobox',
      }}
    >
      {!options.length && (
        <MenuItem disabled={true} key="EMPTY" value="EMPTY">
          No options
        </MenuItem>
      )}
      {options.map(option => (
        <MenuItem key={option} value={option}>
          <Checkbox color="primary" checked={fieldValue?.indexOf(option) > -1} />
          <ListItemText primary={option} />
        </MenuItem>
      ))}
    </Select>
  </>
);

export default MultiSelectFilter;
