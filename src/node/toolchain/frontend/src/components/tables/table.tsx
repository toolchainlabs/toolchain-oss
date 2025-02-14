/*
Copyright 2019 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useState, useEffect, Fragment } from 'react';
import { useParams } from 'react-router-dom';
import RefreshSharpIcon from '@mui/icons-material/RefreshSharp';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import TabContext from '@mui/lab/TabContext';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import MuiTable from '@mui/material/Table';
import TableRow from '@mui/material/TableRow';
import TableCell from '@mui/material/TableCell';
import TableBody from '@mui/material/TableBody';
import TableSortLabel from '@mui/material/TableSortLabel';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import Chip from '@mui/material/Chip';
import FilterList from '@mui/icons-material/FilterList';
import Sort from '@mui/icons-material/Sort';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import Link from '@mui/material/Link';
import Button from '@mui/material/Button';
import OpenInBrowser from '@mui/icons-material/OpenInBrowser';
import { Theme, styled, keyframes, alpha, useTheme } from '@mui/material/styles';
import { SystemStyleObject } from '@mui/system/styleFunctionSx';
import useMediaQuery from '@mui/material/useMediaQuery';
import { TableColumns, TableTabFilters, TableFilters } from 'common/interfaces/table';
import { BuildIndicators } from 'common/interfaces/builds';
import CacheIndicators from 'components/cache-indicators/cache-indicators';
import TableFilterDialog from './table-filter-dialog';
import TableSortDialogMobile from './table-sort-dialog-mobile';

export type TableQueryChange = (type: 'reset' | 'update', filters?: { [key: string]: any }) => void;
export type TableProps<T> = {
  columns: TableColumns<T>;
  data: { [key: string]: T | string }[];
  filters?: TableFilters;
  isLastPage?: boolean;
  showIndicators?: boolean;
  maxPaginationReached?: boolean;
  sort?: { order: 'asc' | 'desc'; orderBy: string };
  name: string;
  isLoading?: boolean;
  isLoadingIndicators?: boolean;
  tabFilters?: TableTabFilters;
  currentTab?: string;
  isLoadingNext?: boolean;
  onQueryChange?: TableQueryChange;
  refreshData?: () => void;
  onRowClick?: (e: React.MouseEvent<HTMLElement>, data: any) => void;
  onOpenNewTabClick?: (e: React.MouseEvent<HTMLElement>, data: any) => void;
  setCurrentTab?: (value: string) => void;
  fetchNext?: () => void;
  rowStyles?: (theme?: Theme) => SystemStyleObject<Theme>;
  bodyRowStyles?: (theme?: Theme) => SystemStyleObject<Theme>;
  indicators?: BuildIndicators;
};

const StyledRowBox = styled(Box)(({ theme }) => ({
  backgroundColor: theme.palette.common.white,
  borderRadius: theme.spacing(1),
  padding: `0 ${theme.spacing(1)}`,
  marginBottom: theme.spacing(0.5),
  [theme.breakpoints.down('md')]: {
    overflow: 'hidden',
  },
}));

const StyledFilterBox = styled(StyledRowBox)(({ theme }) => ({
  padding: `${theme.spacing(0.5)} ${theme.spacing(2)}`,
  minHeight: 35,
}));

const StyledIndicatorsBox = styled(StyledFilterBox)(({ theme }) => ({
  padding: '6.61px 21px',
  marginLeft: theme.spacing(0.5),
}));

const StyledFooterBox = styled(StyledRowBox)(({ theme }) => ({
  padding: theme.spacing(1),
}));

const StyledTableRow = styled(StyledRowBox.withComponent(TableRow))(({ theme }) => ({
  [`& td`]: {
    [`&:first-of-type`]: {
      borderTopLeftRadius: theme.spacing(1),
      borderBottomLeftRadius: theme.spacing(1),
    },
    [`&:last-of-type`]: {
      borderTopRightRadius: theme.spacing(1),
      borderBottomRightRadius: theme.spacing(1),
    },
  },
}));

const StyledTableBody = styled(TableBody)(({ theme }) => ({
  [`& td`]: {
    padding: `10px ${theme.spacing(2)}`,
  },
}));

const StyledTabs = styled(Tabs)(({ theme }) => ({
  [`& .MuiTabs-indicator`]: {
    display: 'flex',
    justifyContent: 'center',
    backgroundColor: 'transparent',
    [`& span`]: { border: `1px solid ${theme.palette.primary.main}`, width: 81 },
  },
  [`& .MuiTab-root`]: {
    minWidth: 'unset',
    padding: `10px ${theme.spacing(2)}`,
  },
  [`& .Mui-selected`]: {
    color: theme.palette.primary.main,
  },
}));

const getColorAnimationKeyframes = (main: string, light: string) =>
  keyframes({
    '0%': {
      fill: main,
      color: main,
    },
    '50%': {
      fill: light,
      color: light,
    },
    '70%': {
      fill: light,
      color: light,
    },
    '100%': {
      fill: main,
      color: main,
    },
  });

const StyledSvg = styled('svg')(({ theme }) => {
  const rotateAnimation = keyframes({
    '0%': {
      transform: 'rotate(0deg)',
    },
    '70%': {
      transform: 'rotate(180deg)',
    },
    '100%': {
      transform: 'rotate(180deg)',
    },
  });

  const changeColorAnimation = getColorAnimationKeyframes(theme.palette.primary.main, theme.palette.primary.light);

  return {
    marginRight: theme.spacing(0.5),
    animation: `${rotateAnimation} 2s ${theme.transitions.easing.easeInOut} 0s infinite`,
    [`& path`]: {
      animation: `${changeColorAnimation} 2s ${theme.transitions.easing.easeInOut} 0s infinite`,
    },
  };
});

const StyledLoadingTypography = styled(Typography)(({ theme }) => {
  const changeColorAnimation = getColorAnimationKeyframes(theme.palette.primary.main, theme.palette.primary.light);

  return {
    animation: `${changeColorAnimation} 2s ${theme.transitions.easing.easeInOut} 0s infinite`,
  };
});

const StyledPaper = styled(Paper)(({ theme }) => ({
  border: 0,
  borderRadius: 8,
  backgroundColor: theme.palette.grey[50],
  padding: theme.spacing(10),
}));

const StyledTableHead = styled(TableHead)(({ theme }) => ({
  [`& td`]: {
    padding: `12px ${theme.spacing(2)}`,
  },
  border: 0,
  borderRadius: 8,
  [theme.breakpoints.down('md')]: {
    display: 'none',
  },
}));

const StyledTableRowSpacer = styled(TableRow)(({ theme }) => ({
  height: theme.spacing(0.5),
  [`&:last-of-type`]: {
    [theme.breakpoints.down('md')]: {
      display: 'none',
    },
  },
}));

const StyledHiddenSpan = styled('span')(() => ({
  border: 0,
  clip: 'rect(0 0 0 0)',
  height: 1,
  margin: -1,
  overflow: 'hidden',
  padding: 0,
  position: 'absolute',
  top: 20,
  width: 1,
}));

const StyledFilterChip = styled(Chip)(({ theme }) => ({
  color: theme.palette.text.primary,
  [`& .MuiChip-deleteIcon`]: {
    color: alpha(theme.palette.primary.contrastText, 0.7),
    [`&:hover`]: {
      color: theme.palette.primary.contrastText,
    },
  },
}));

const StyledFilterChipClearAll = styled(StyledFilterChip)(() => ({
  cursor: 'pointer',
}));

const StyledMuiTable = styled(MuiTable)(({ theme }) => ({
  borderCollapse: 'separate',
  [theme.breakpoints.down('md')]: {
    borderRadius: 8,
    overflow: 'hidden',
  },
}));

const StyledTableSortLabel = styled(TableSortLabel)(() => ({
  [`& .MuiTableSortLabel-icon`]: {
    position: 'absolute',
    right: -30,
  },
}));

const StyledIconButtonSort = styled(IconButton)(({ theme }) => ({
  display: 'block',
  backgroundColor: theme.palette.grey[200],
  borderRadius: '4px',
  width: '100%',
  padding: '6px 0',
  marginBottom: theme.spacing(0.5),
}));

const Table = <T,>({
  columns,
  filters = null,
  data,
  sort,
  isLoading,
  tabFilters,
  currentTab,
  setCurrentTab,
  onRowClick,
  onQueryChange,
  refreshData,
  fetchNext,
  isLoadingNext,
  isLastPage,
  maxPaginationReached,
  onOpenNewTabClick,
  name,
  rowStyles,
  bodyRowStyles,
  indicators,
  showIndicators = false,
  isLoadingIndicators,
}: TableProps<T>) => {
  const [open, setOpen] = useState(false);
  const [isSortDialogOpen, setIsSortDialogOpen] = useState<boolean>(false);
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const { order, orderBy } = sort;
  const { repoSlug } = useParams();
  const showTopRow = showIndicators || !!filters;

  useEffect(() => {
    setOpen(false);
  }, [repoSlug]);

  const openFilters = () => {
    setOpen(true);
  };

  const closeFilters = () => {
    setOpen(false);
  };

  const clearAllFilters = () => onQueryChange('reset');

  const removeFilter = (key: string, filterName: string) =>
    onQueryChange('update', { [filterName]: filters[key].noFilterValue });

  const loadMore = (e: React.SyntheticEvent) => {
    e.preventDefault();

    fetchNext();
  };

  const scrollToTop = () =>
    window.scrollTo({
      top: 0,
      behavior: 'smooth',
    });

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const handleRequestSort = (property: any) => (event: React.MouseEvent<unknown>) => {
    const isAsc = orderBy === property && order === 'asc';
    const sortPrefix = isAsc ? '-' : '';
    onQueryChange('update', { sort: `${sortPrefix}${property}` });
  };

  const TableFilterTabs = ({ tabs, current }: { tabs: TableTabFilters; current: string }) => (
    <TabContext value={current}>
      <StyledTabs
        value={current}
        variant="scrollable"
        scrollButtons="auto"
        indicatorColor="primary"
        textColor="inherit"
        onChange={(event, value) => {
          setCurrentTab(value);
        }}
        TabIndicatorProps={{ children: <span /> }}
      >
        {Object.keys(tabs).map(key => (
          <Tab key={key} label={tabs[key].label} value={key} title={tabs[key].label} />
        ))}
      </StyledTabs>
    </TabContext>
  );

  const shouldRenderBody = data?.length && !isLoading;

  const HexagonSpinner = () => (
    <StyledSvg width="19" height="20" viewBox="0 0 19 20" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M9.5 0L18.1603 5V15L9.5 20L0.839746 15V5L9.5 0Z" fill="#00A9B7" />
    </StyledSvg>
  );

  const TableFooter = () => {
    const hasPagination = !!fetchNext;
    const loadMoreOrBackToTop = !isLastPage ? (
      <Grid container justifyContent="center" alignItems="center">
        <Link href="#" onClick={loadMore}>
          <Typography variant="body2" color="primary">
            Load more
          </Typography>
        </Link>
      </Grid>
    ) : (
      <>
        <Grid container spacing={2} alignItems="center">
          <Grid item>
            <Typography variant="caption">
              {maxPaginationReached ? 'Maximum page number reached' : `All ${name} are loaded`}
            </Typography>
          </Grid>
          <Grid item>
            <Button color="primary" onClick={scrollToTop}>
              BACK TO TOP
            </Button>
          </Grid>
        </Grid>
      </>
    );

    if (!shouldRenderBody) {
      const noDatamessage = tabFilters ? tabFilters[currentTab].noDataText : `No ${name} found`;
      const message = isLoading ? `Loading ${name}...` : noDatamessage;

      return (
        <StyledPaper elevation={0}>
          <Grid container justifyContent="center">
            <Grid>
              <Typography variant="h3" color="text.disabled">
                {message}
              </Typography>
            </Grid>
          </Grid>
        </StyledPaper>
      );
    }

    return hasPagination ? (
      <StyledFooterBox>
        <Grid container justifyContent="center" alignItems="center">
          <Grid item>
            {isLoadingNext ? (
              <Grid container alignItems="center" justifyContent="center">
                <HexagonSpinner />
                <StyledLoadingTypography variant="caption" color="primary">
                  Loading
                </StyledLoadingTypography>
              </Grid>
            ) : (
              loadMoreOrBackToTop
            )}
          </Grid>
        </Grid>
      </StyledFooterBox>
    ) : null;
  };

  const areEqualValues = (value1: any, value2: any) => JSON.stringify(value1) === JSON.stringify(value2);

  const isSortable = columns && Object.values(columns).some(value => value.sortable);
  const sortableColumns = Object.values(columns)
    .filter(value => value.sortable)
    .map(el => ({
      sortName: el.sortName,
      label: el.label,
    }));

  const hasActiveFilters =
    filters &&
    Object.values(filters).filter(
      currFilter => currFilter.value && !areEqualValues(currFilter.value, currFilter.noFilterValue)
    ).length > 0;

  const getSortDetailsLabel = () => {
    if (!sort?.orderBy) {
      return '';
    }
    const sortColumnName = sortableColumns.find(column => column.sortName === sort.orderBy)?.label;

    return `: ${sortColumnName} ${sort.order === 'asc' ? '↑' : '↓'}`;
  };

  return (
    <>
      {filters && (
        <StyledRowBox>
          <Grid container justifyContent="space-between">
            <Grid item>{tabFilters && <TableFilterTabs tabs={tabFilters} current={currentTab} />}</Grid>
            <Grid item>
              <Grid container>
                <Grid item>
                  <Tooltip title="Show filters">
                    <IconButton color="primary" aria-label="show filters" onClick={openFilters} size="large">
                      <FilterList />
                    </IconButton>
                  </Tooltip>
                </Grid>
                <Grid>
                  <Tooltip title="Refresh Table">
                    <span>
                      <IconButton
                        color="primary"
                        disabled={isLoading}
                        onClick={refreshData}
                        aria-label="refresh"
                        size="large"
                      >
                        <RefreshSharpIcon />
                      </IconButton>
                    </span>
                  </Tooltip>
                </Grid>
              </Grid>
            </Grid>
          </Grid>
        </StyledRowBox>
      )}
      {showTopRow ? (
        <Grid container alignItems="center">
          <Grid item xs>
            <StyledFilterBox>
              <Grid container spacing={1}>
                {hasActiveFilters && (
                  <>
                    {Object.keys(filters).map(key => {
                      const { name: filterName, value, chipRender } = filters[key];

                      return (
                        value &&
                        !areEqualValues(value, filters[key].noFilterValue) && (
                          <Grid item key={filterName}>
                            <StyledFilterChip
                              color="primary"
                              label={<Typography variant="caption">{chipRender(value)}</Typography>}
                              size="small"
                              onDelete={() => removeFilter(key, filterName)}
                            />
                          </Grid>
                        )
                      );
                    })}
                    <Grid item>
                      <StyledFilterChipClearAll
                        variant="outlined"
                        color="primary"
                        label={<Typography variant="caption">clear all</Typography>}
                        size="small"
                        onClick={clearAllFilters}
                      />
                    </Grid>
                  </>
                )}
              </Grid>
            </StyledFilterBox>
          </Grid>
          <Grid item xs="auto">
            <StyledIndicatorsBox>
              <CacheIndicators indicators={indicators} displayTimeSaved={false} loading={isLoadingIndicators} />
            </StyledIndicatorsBox>
          </Grid>
        </Grid>
      ) : null}
      {isMobile ? (
        <StyledIconButtonSort color="primary" aria-label="sort" size="medium" onClick={() => setIsSortDialogOpen(true)}>
          <Grid container justifyContent="center" alignItems="center">
            <Grid item>
              <Sort />
            </Grid>
            <Grid item>
              <Typography variant="button1">{`sort${getSortDetailsLabel()}`}</Typography>
            </Grid>
          </Grid>
        </StyledIconButtonSort>
      ) : null}
      <TableContainer>
        <StyledMuiTable aria-label="table" role="grid">
          <StyledTableHead>
            <StyledTableRow sx={rowStyles}>
              {Object.keys(columns).map(key => {
                const { sortable, sortName, label } = columns[key];

                return (
                  <TableCell key={key} component="td" scope="row" sx={{ width: columns[key].width }}>
                    {sortable ? (
                      <StyledTableSortLabel
                        active={orderBy === sortName}
                        direction={orderBy === sortName ? order : 'asc'}
                        onClick={handleRequestSort(sortName)}
                      >
                        <Typography variant="overline" color="textSecondary">
                          {label}
                        </Typography>
                        {orderBy === sortName ? (
                          <StyledHiddenSpan>
                            {order === 'desc' ? 'sorted descending' : 'sorted ascending'}
                          </StyledHiddenSpan>
                        ) : null}
                      </StyledTableSortLabel>
                    ) : (
                      <Typography variant="overline" color="textSecondary">
                        {label}
                      </Typography>
                    )}
                  </TableCell>
                );
              })}
            </StyledTableRow>
            <StyledTableRowSpacer />
          </StyledTableHead>
          <StyledTableBody>
            {shouldRenderBody
              ? data.map(row => (
                  <Fragment key={`table-row-${row.id}`}>
                    <StyledTableRow
                      onClick={e => !!onRowClick && onRowClick(e, row[Object.keys(row).filter(key => key !== 'id')[0]])}
                      sx={[bodyRowStyles, rowStyles]}
                    >
                      {Object.keys(row)
                        .filter(key => key !== 'id')
                        .map(key => (
                          <TableCell key={key} component="td" scope="row">
                            {columns[key].renderValue(row[key] as T)}
                          </TableCell>
                        ))}
                      {onOpenNewTabClick && (
                        <TableCell component="td" scope="row">
                          <Button
                            onClick={e => onOpenNewTabClick(e, row[Object.keys(row).filter(key => key !== 'id')[0]])}
                            startIcon={<OpenInBrowser fontSize="small" color="primary" />}
                          >
                            <Typography variant="button2" color="primary">
                              OPEN NEW TAB
                            </Typography>
                          </Button>
                        </TableCell>
                      )}
                    </StyledTableRow>
                    <StyledTableRowSpacer />
                  </Fragment>
                ))
              : null}
          </StyledTableBody>
        </StyledMuiTable>
      </TableContainer>
      <TableFooter />
      {filters && (
        <TableFilterDialog isOpen={open} closeDialog={closeFilters} filterList={filters} updateQuery={onQueryChange} />
      )}
      {isSortable && isMobile ? (
        <TableSortDialogMobile
          isOpen={isSortDialogOpen}
          closeDialog={() => setIsSortDialogOpen(false)}
          columns={sortableColumns}
          updateQuery={onQueryChange}
          sort={sort}
        />
      ) : null}
    </>
  );
};

export default Table;
