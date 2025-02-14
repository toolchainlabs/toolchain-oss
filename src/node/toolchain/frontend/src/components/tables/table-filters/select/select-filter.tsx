/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import InputLabel from '@mui/material/InputLabel';
import Select from '@mui/material/Select';
import Input from '@mui/material/Input';
import MenuItem from '@mui/material/MenuItem';

import OutcomeType from 'common/enums/OutcomeType';
import { BuildOutcome } from 'components/icons/build-outcome';

type SelectFilterProps = {
  fieldValue: string;
  onChange: (formField: { [key: string]: string | string[] }) => void;
  fieldName: string;
  fieldLabel: string;
  options: string[];
};

const SelectFilter = ({ fieldValue, onChange, fieldName, fieldLabel, options = [] }: SelectFilterProps) => {
  const isOutcomeType = options.includes(OutcomeType.SUCCESS);

  return (
    <>
      <InputLabel id={fieldName}>{fieldLabel}</InputLabel>
      <Select
        fullWidth
        value={fieldValue || 'ALL'}
        name={fieldName}
        onChange={event => {
          const eventValue = event.target.value;
          const value = eventValue === 'ALL' ? undefined : (eventValue as string);

          onChange({ [fieldName]: value });
        }}
        input={<Input name={fieldName} id={fieldName} />}
        SelectDisplayProps={{
          role: 'combobox',
        }}
      >
        <MenuItem value="ALL" key="ALL">
          All
        </MenuItem>
        {options.map((option: string) => (
          <MenuItem value={option} key={option}>
            {isOutcomeType ? <BuildOutcome outcome={option as OutcomeType} chipVariant="noborder" /> : option}
          </MenuItem>
        ))}
      </Select>
    </>
  );
};

export default SelectFilter;
