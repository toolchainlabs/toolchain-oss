/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useState, useEffect } from 'react';
import dayjs from 'dayjs';
import durationPlugin from 'dayjs/plugin/duration';
import Slider from '@mui/material/Slider';
import Grid from '@mui/material/Grid';
import InfoOutlined from '@mui/icons-material/InfoOutlined';
import Typography from '@mui/material/Typography';
import Tooltip from '@mui/material/Tooltip';
import TextField from '@mui/material/TextField';
import Select, { SelectChangeEvent } from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import { RUN_TIME_FROM_SLIDER_MARKS, RUN_TIME_TO_SLIDER_MARKS } from 'utils/runtime-marks';
import { styled } from '@mui/material/styles';

dayjs.extend(durationPlugin);

const enum RunTimeType {
  FROM = 'runTypeFrom',
  TO = 'runTypeTo',
  ALL = 'all',
}

const filterDirectionArray: { label: string; value: string }[] = [
  {
    label: 'is longer than',
    value: RunTimeType.FROM,
  },
  {
    label: 'is shorter than',
    value: RunTimeType.TO,
  },
  {
    label: 'all',
    value: RunTimeType.ALL,
  },
];

type SelectProps = {
  isLong: boolean;
};

type SliderProps = {
  isFilterActive: boolean;
};

const SliderContainer = styled(Grid)(({ theme }) => ({
  [theme.breakpoints.down('md')]: {
    width: '100%',
    marginTop: theme.spacing(3),
    paddingBottom: theme.spacing(3),
  },
}));

const RunTimeContainer = styled(Grid)(({ theme }) => ({
  border: 0,
  borderRadius: 8,
  backgroundColor: theme.palette.grey[50],
  padding: theme.spacing(3),
  width: '100%',
  margin: '0 auto',
}));

const InputFields = styled(Grid)(({ theme }) => ({
  marginRight: theme.spacing(3),
}));

const InfoIcon = styled(InfoOutlined)(({ theme }) => ({
  cursor: 'pointer',
  position: 'relative',
  top: 3,
  fontSize: 20,
  color: theme.palette.text.secondary,
}));

const StyledTextField = styled(TextField)(({ theme }) => ({
  width: theme.spacing(5),
  '& .MuiFormHelperText-root': {
    position: 'absolute',
    bottom: '-20px',
  },
}));

const CustomSelect = styled(Select, { shouldForwardProp: propName => propName !== 'isLong' })<SelectProps>(
  ({ isLong }) => ({
    width: isLong ? 260 : 144,
    paddingRight: `0 !important`,
  })
);

const StyledSlider = styled(Slider, { shouldForwardProp: propName => propName !== 'isFilterActive' })<SliderProps>(
  ({ theme, isFilterActive }) => ({
    '&.MuiSlider-root': {
      position: 'relative',
      top: 35,
      width: 400,
      [theme.breakpoints.down('md')]: {
        width: '100%',
      },
    },
    '& .MuiSlider-markLabel': {
      fontSize: 12,
    },
    '& .MuiSlider-valueLabel': {
      marginTop: 9,
      lineHeight: 1.2,
      fontSize: 12,
      background: 'unset',
      padding: 0,
      width: 32,
      height: 32,
      borderRadius: '50% 50% 50% 0',
      backgroundColor: theme.palette.primary.main,
      transformOrigin: 'bottom left',
      transform: 'translate(50%, -100%) rotate(-45deg) scale(0)',
      '&:before': { display: 'none' },
      '&.MuiSlider-valueLabelOpen': {
        transform: 'translate(50%, -100%) rotate(-45deg) scale(1)',
      },
      '& > *': {
        transform: 'rotate(45deg)',
      },
    },
    '& >.MuiSlider-thumb': {
      display: isFilterActive ? 'flex' : 'none',
    },
  })
);

type RunTimeFilterProps = {
  fieldValue: string[];
  onChange: (formField: { [key: string]: string | string[] }) => void;
  fieldName: string;
  fieldLabel: string;
};

const RunTimeFilter = ({
  fieldValue = [undefined, undefined],
  onChange,
  fieldName,
  fieldLabel,
}: RunTimeFilterProps) => {
  const [filterDirection, setFilterDirection] = useState<string>(RunTimeType.ALL);
  const [isResetBlocked, setIsResetBlocked] = useState<boolean>(false);

  const maxNumOfSeconds = 60;
  const maxNumOfMinutes = 360;

  const [rangeFrom, rangeTo] = fieldValue;

  const rangeFromInMinutes = Math.floor(dayjs.duration({ seconds: +rangeFrom }).asMinutes()).toString();

  const displayValue = (rangeFrom ? rangeFromInMinutes : rangeTo) || '0';
  const maxValue = filterDirection === RunTimeType.TO ? maxNumOfSeconds : maxNumOfMinutes;

  const selectedMarks = filterDirection === RunTimeType.TO ? RUN_TIME_TO_SLIDER_MARKS : RUN_TIME_FROM_SLIDER_MARKS;
  const isFilterActive = filterDirection !== RunTimeType.ALL;

  useEffect(() => {
    if (rangeFrom !== undefined) {
      setFilterDirection(RunTimeType.FROM);
    } else if (rangeTo !== undefined) {
      setFilterDirection(RunTimeType.TO);
    } else if (rangeFrom === undefined && rangeTo === undefined && !isResetBlocked) {
      setFilterDirection(RunTimeType.ALL);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rangeFrom, rangeTo]);

  const convertSingleValueToFilterReadable = (value: number | string) => (!value ? undefined : value.toString());

  const convertValueToFilterReadable = ([inputRangeFrom, inputRangeTo]: Array<number | string>) => {
    const validRangeFrom = convertSingleValueToFilterReadable(inputRangeFrom);
    const validRangeTo = convertSingleValueToFilterReadable(inputRangeTo);
    return [validRangeFrom, validRangeTo];
  };

  const onChangeFilterDirectionHandler = (e: SelectChangeEvent<unknown>) => {
    if (e.target.value === RunTimeType.ALL) {
      onChange({ [fieldName]: convertValueToFilterReadable([undefined, undefined]) });
    } else if (e.target.value === RunTimeType.FROM) {
      onChange({ [fieldName]: convertValueToFilterReadable(['0', undefined]) });
    } else {
      onChange({ [fieldName]: convertValueToFilterReadable([undefined, '0']) });
    }

    setFilterDirection(e.target.value as string);
  };

  const handleInputChange = (event: React.ChangeEvent<{ name: string; value: string }>) => {
    const { name, value } = event.target;

    if (name === RunTimeType.FROM) {
      const isValidFromValue = +value >= 0 && +value <= maxNumOfMinutes;
      if (!isValidFromValue) {
        return;
      }

      const calculatedValue = dayjs.duration({ minutes: +value }).asSeconds();
      onChange({ [fieldName]: convertValueToFilterReadable([calculatedValue, undefined]) });
      if (calculatedValue === 0) {
        setFilterDirection(RunTimeType.ALL);
      }
    } else {
      const isValidToValue = +value >= 0 && +value <= maxNumOfSeconds;
      if (!isValidToValue) {
        return;
      }

      onChange({ [fieldName]: convertValueToFilterReadable([undefined, value]) });
      if (value === '0') {
        setFilterDirection(RunTimeType.ALL);
      }
    }
  };

  const onSliderChangeHandler = (_: Event, value: number | number[]) => {
    if (filterDirection === RunTimeType.TO) {
      onChange({ [fieldName]: convertValueToFilterReadable([0, value as number]) });
    } else if (filterDirection === RunTimeType.FROM) {
      onChange({
        [fieldName]: convertValueToFilterReadable([dayjs.duration({ minutes: value as number }).asSeconds(), 0]),
      });
    }
  };

  return (
    <RunTimeContainer container>
      <InputFields item>
        <Grid container spacing={2} direction="column">
          <Grid item>
            <Grid container alignItems="center" spacing={1}>
              <Grid item>
                <Typography variant="subtitle1">{fieldLabel}</Typography>
              </Grid>
              {filterDirection !== RunTimeType.ALL && (
                <Grid item>
                  <Tooltip
                    title={`Enter filter value in ${filterDirection === RunTimeType.TO ? 'seconds' : 'minutes'}`}
                    placement="top"
                    arrow
                  >
                    <InfoIcon />
                  </Tooltip>
                </Grid>
              )}
            </Grid>
          </Grid>
          <Grid item>
            <Grid container spacing={1} direction="row" alignItems="flex-end">
              <Grid item>
                <CustomSelect
                  id="standard-select-filter-native"
                  value={filterDirection}
                  onChange={onChangeFilterDirectionHandler}
                  isLong={!isFilterActive}
                >
                  {filterDirectionArray.map(option => (
                    <MenuItem key={option.value} value={option.value}>
                      {option.label}
                    </MenuItem>
                  ))}
                </CustomSelect>
              </Grid>
              {filterDirection === RunTimeType.FROM && (
                <>
                  <Grid item>
                    <StyledTextField
                      id="fromInput"
                      name={RunTimeType.FROM}
                      value={displayValue}
                      InputProps={{ type: 'number' }}
                      margin="none"
                      onChange={handleInputChange}
                    />
                  </Grid>
                  <Grid item>
                    <Typography variant="body1">minutes</Typography>
                  </Grid>
                </>
              )}
              {filterDirection === RunTimeType.TO && (
                <>
                  <Grid item>
                    <StyledTextField
                      id="toInput"
                      name={RunTimeType.TO}
                      value={displayValue}
                      InputProps={{ type: 'number' }}
                      margin="none"
                      onChange={handleInputChange}
                    />
                  </Grid>
                  <Grid item>
                    <Typography variant="body1">seconds</Typography>
                  </Grid>
                </>
              )}
            </Grid>
          </Grid>
        </Grid>
      </InputFields>
      <SliderContainer item>
        <StyledSlider
          isFilterActive={isFilterActive}
          value={+displayValue}
          name={fieldName}
          step={1}
          aria-labelledby={fieldName}
          valueLabelDisplay="on"
          defaultValue={0}
          min={0}
          max={maxValue}
          marks={selectedMarks}
          disabled={!isFilterActive}
          onChange={onSliderChangeHandler}
          onMouseDown={() => setIsResetBlocked(true)}
          onMouseUp={() => setIsResetBlocked(false)}
        />
      </SliderContainer>
    </RunTimeContainer>
  );
};

export default RunTimeFilter;
