/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useState, useEffect, Fragment } from 'react';
import Dialog from '@mui/material/Dialog';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Grid from '@mui/material/Grid';
import Close from '@mui/icons-material/Close';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import NativeSelect from '@mui/material/NativeSelect';
import Button from '@mui/material/Button';
import { styled } from '@mui/material/styles';

type SortSettingsType = { order: 'asc' | 'desc'; orderBy: string | null };

type TableSortDialogProps = {
  isOpen: boolean;
  closeDialog: () => void;
  columns: Array<{ label: string; sortName: string }>;
  sort?: SortSettingsType;
  updateQuery: (type: 'reset' | 'update', values?: any) => void;
};

const StyledDialogContent = styled(DialogContent)(({ theme }) => ({ padding: theme.spacing(2) }));
const StyledDialogTitle = styled(DialogTitle)(({ theme }) => ({ marginTop: theme.spacing(7), padding: 16 }));
const StyledCloseButton = styled(IconButton)(() => ({ padding: 0 }));

const defaultSelectState: SortSettingsType = { order: 'asc', orderBy: null };

function TableSortDialog({ isOpen, closeDialog, sort, columns, updateQuery }: TableSortDialogProps) {
  const [localSort, setLocalSort] = useState<SortSettingsType>(defaultSelectState);

  useEffect(() => {
    setLocalSort(sort);
  }, [sort]);

  const onSelectChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const { value } = e.target;
    setLocalSort(JSON.parse(value));
  };

  const handleRequestSort = () => {
    const isAsc = localSort?.order === 'asc';
    const sortPrefix = !isAsc ? '-' : '';
    if (localSort?.orderBy) {
      updateQuery('update', { sort: `${sortPrefix}${localSort.orderBy}` });
    } else {
      updateQuery('update', { sort: undefined });
    }

    closeDialog();
  };

  const selectValue = JSON.stringify(localSort);
  const hasValueChanged = localSort?.order !== sort.order || localSort?.orderBy !== sort.orderBy;

  return (
    <Dialog open={isOpen} onClose={closeDialog} fullScreen>
      <StyledDialogTitle>
        <Grid container justifyContent="space-between">
          <Grid item>
            <Typography variant="h3">Sort By</Typography>
          </Grid>
          <Grid item>
            <StyledCloseButton color="primary" onClick={closeDialog} size="large">
              <Close />
            </StyledCloseButton>
          </Grid>
        </Grid>
      </StyledDialogTitle>
      <StyledDialogContent>
        <Grid container spacing={4}>
          <Grid item xs={12}>
            <NativeSelect fullWidth={true} onChange={onSelectChange} value={selectValue} name="Sort Select">
              <option value={JSON.stringify(defaultSelectState)}>Default</option>
              {columns.map(column => (
                <Fragment key={column.sortName}>
                  <option value={JSON.stringify({ order: 'asc', orderBy: column.sortName })}>{column.label} ↓</option>
                  <option value={JSON.stringify({ order: 'desc', orderBy: column.sortName })}>{column.label} ↑</option>
                </Fragment>
              ))}
            </NativeSelect>
          </Grid>
          <Grid item xs={12}>
            <Grid container alignItems="center" justifyContent="flex-end" spacing={5}>
              <Grid item>
                <Button color="primary" onClick={() => setLocalSort(defaultSelectState)} disabled={!localSort?.orderBy}>
                  <Typography variant="button">Reset to default</Typography>
                </Button>
              </Grid>
              <Grid item>
                <Button onClick={handleRequestSort} variant="contained" color="primary" disabled={!hasValueChanged}>
                  <Typography variant="button">Apply sorting</Typography>
                </Button>
              </Grid>
            </Grid>
          </Grid>
        </Grid>
      </StyledDialogContent>
    </Dialog>
  );
}

export default TableSortDialog;
