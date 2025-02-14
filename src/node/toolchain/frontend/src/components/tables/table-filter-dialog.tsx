/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useState, useEffect } from 'react';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import Button from '@mui/material/Button';
import CloseIcon from '@mui/icons-material/Close';
import Grid from '@mui/material/Grid';
import FormControl from '@mui/material/FormControl';
import { styled } from '@mui/material/styles';

import { FormFieldValue, TableFilters } from 'common/interfaces/table';

type FilterValues = { [key: string]: any };

type TableFilterDialogProps = {
  isOpen: boolean;
  closeDialog: () => void;
  filterList: TableFilters;
  updateQuery: (type: 'reset' | 'update', values?: any) => void;
};

const StyledDialog = styled(Dialog)(({ theme }) => ({
  [theme.breakpoints.down('md')]: {
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'flex-start',
    zIndex: '1303 !important',
  },
  ['& .MuiDialog-container']: {
    [theme.breakpoints.down('md')]: {
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'flex-start',
    },
  },
  ['& .MuiPaper-root']: {
    left: 40,
    width: 800,
    maxWidth: 800,
    borderRadius: 8,
    boxShadow: `0px 0px 40px rgba(0, 169, 183, 0.5)`,
    [theme.breakpoints.down('md')]: {
      borderRadius: 0,
      left: 0,
      top: 0,
      boxShadow: 'unset',
      margin: 0,
      height: '100vh',
      maxHeight: 'unset',
      width: '100%',
      overflowY: 'auto',
    },
  },
  ['& .MuiBackdrop-root']: {
    backgroundColor: theme.palette.grey[100],
  },
}));

const StyledDialogTitle = styled(DialogTitle)(({ theme }) => ({
  padding: theme.spacing(3),
  [theme.breakpoints.down('md')]: {
    padding: `${theme.spacing(2)} ${theme.spacing(2)} ${theme.spacing(5)} ${theme.spacing(2)}`,
  },
}));

const StyledDialogActions = StyledDialogTitle.withComponent(DialogActions);

const StyledDialogContent = styled(DialogContent)(({ theme }) => ({
  overflowY: 'unset',
  padding: `${theme.spacing(1)} ${theme.spacing(3)}`,
  [theme.breakpoints.down('md')]: {
    padding: `0 ${theme.spacing(2)} ${theme.spacing(2)}`,
    overflowY: 'unset',
  },
}));

const StyledCloseIcon = styled(CloseIcon)(() => ({
  fontSize: 20,
}));

const StyledActionContiner = styled(Grid)(({ theme }) => ({
  justifyContent: 'flex-end',
  [theme.breakpoints.down('md')]: {
    justifyContent: 'space-between',
  },
}));

const StyledIconButton = styled(IconButton)(() => ({
  padding: 10,
}));

const getFilterValues = (filters: FilterValues): FormFieldValue =>
  Object.keys(filters).reduce((acc, key) => ({ ...acc, [filters[key].name]: filters[key].value }), {});

const TableFilterDialog = ({ isOpen, closeDialog, filterList, updateQuery }: TableFilterDialogProps) => {
  const [formValues, setFormValues] = useState<FormFieldValue>(getFilterValues(filterList));

  const areEqualValues = (value1: any, value2: any) => JSON.stringify(value1) === JSON.stringify(value2);

  const isFormChanged = !areEqualValues(formValues, getFilterValues(filterList));

  const findNoFilterValue = (name: string) => {
    const selectedKey = Object.keys(filterList).find(key => filterList[key].name === name);
    return filterList[selectedKey].noFilterValue;
  };

  const hasActiveFilters = Object.keys(formValues).some(
    key => !!formValues[key] && !areEqualValues(formValues[key], findNoFilterValue(key))
  );

  useEffect(() => {
    setFormValues(getFilterValues(filterList));
  }, [filterList]);

  const updateFormValues = (field: FormFieldValue) => {
    setFormValues({ ...formValues, ...field });
  };

  const handleClear = () => {
    const emptyValues = { ...formValues };
    Object.keys(emptyValues).forEach(key => {
      emptyValues[key] = findNoFilterValue(key);
    });
    setFormValues(emptyValues);
  };

  const handleUpdate = () => {
    updateQuery('update', formValues);
    closeDialog();
  };

  const handleClose = () => {
    setFormValues(getFilterValues(filterList));
    closeDialog();
  };

  return (
    <StyledDialog onClose={closeDialog} aria-labelledby="table-dialog-title" open={isOpen}>
      <StyledDialogTitle id="table-dialog-title">
        <Grid container alignItems="center" justifyContent="space-between">
          <Grid item>
            <Typography variant="h3">Filters</Typography>
          </Grid>
          <Grid item>
            <StyledIconButton aria-label="close filters" onClick={handleClose}>
              <StyledCloseIcon color="primary" />
            </StyledIconButton>
          </Grid>
        </Grid>
      </StyledDialogTitle>
      <StyledDialogContent>
        <Grid container spacing={3}>
          {Object.keys(filterList).map(key => {
            const { fullWidth, filterRender, name, label, options } = filterList[key];

            return (
              <Grid key={name} item xs={12} md={fullWidth ? 12 : 6}>
                <FormControl fullWidth>
                  {filterRender(formValues[name], updateFormValues, name, label, options)}
                </FormControl>
              </Grid>
            );
          })}
        </Grid>
      </StyledDialogContent>
      <StyledDialogActions>
        <StyledActionContiner container spacing={5}>
          <Grid item>
            <Button onClick={handleClear} disabled={!hasActiveFilters} color="primary">
              <Typography variant="button">CLEAR ALL</Typography>
            </Button>
          </Grid>
          <Grid item>
            <Button variant="contained" color="primary" onClick={handleUpdate} disabled={!isFormChanged}>
              <Typography variant="button">APPLY FILTERS</Typography>
            </Button>
          </Grid>
        </StyledActionContiner>
      </StyledDialogActions>
    </StyledDialog>
  );
};

export default TableFilterDialog;
