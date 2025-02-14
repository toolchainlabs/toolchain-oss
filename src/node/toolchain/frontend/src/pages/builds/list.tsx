/*
Copyright 2019 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useMemo, useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrayParam,
  NumberParam,
  StringParam,
  BooleanParam,
  useQueryParams,
  DecodedValueMap,
  QueryParamConfig,
} from 'use-query-params';
import Avatar from '@mui/material/Avatar';
import Snackbar from '@mui/material/Snackbar';
import Tooltip, { TooltipProps } from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import Grid from '@mui/material/Grid';
import Autocomplete from '@mui/material/Autocomplete';
import TextField from '@mui/material/TextField';
import { captureException } from '@sentry/browser';
import { styled, Theme } from '@mui/material/styles';

import { useBuildsTableFiltersContext } from 'store/builds-filters-store';
import { useOrgAndRepoContext } from 'store/org-repo-store';
import { useRequestErrorContext } from 'store/request-error-store';
import { useUserContext } from 'store/user-store';
import Table, { TableQueryChange } from 'components/tables/table';
import RunTimeFilter from 'components/tables/table-filters/run-time/run-time-filter';
import SelectFilter from 'components/tables/table-filters/select/select-filter';
import MultiSelectFilter from 'components/tables/table-filters/multi-select/multi-select-filter';
import PullRequestFilter from 'components/tables/table-filters/title/title-filter';
import AvatarChip from 'components/chips/avatar-chip/avatar-chip';
import TextChip from 'components/chips/text-chip/text-chip';
import ExternalLinkChip from 'components/chips/external-link-chip/external-link-chip';
import BreadCrumbs from 'components/breadrumbs/breadcrumbs';
import VisitScmButton from 'components/visit-scm-button/visit-scm-button';
import backends from 'utils/backend-paths';
import {
  durationToFormat,
  relativeStringToUtcTime,
  utcTimeAgo,
  utcTimeAgoToRelativeString,
  formatTimeFromSeconds,
  extendedDateTimeToLocal,
} from 'utils/datetime-formats';
import { useQueryGet, useQueryOptions, useInfiniteQuery } from 'utils/hooks/query';
import QueryNames from 'common/enums/QueryNames';
import OutcomeType from 'common/enums/OutcomeType';
import { TableTabFilters, TableColumns, TableFilters, TableData } from 'common/interfaces/table';
import paths from 'utils/paths';
import { Build, BuildIndicators, BuildsListResponse } from 'common/interfaces/builds';
import { ToolchainUser, UsersOptionsResponse, UsersOptionsResponseNoBuilds } from 'common/interfaces/builds-options';
import { BuildOutcome, outcomeTexts } from 'components/icons/build-outcome';
import { ApiListResponse } from 'common/interfaces/api';
import { OrgRepoList, OrgList } from 'common/interfaces/orgs-repo';
import OrganizationBanner from 'components/organization-banner/organization-banner';

export type QueryParams = DecodedValueMap<{ [key: string]: QueryParamConfig<any, any> }>;

const UserAvatar = styled(Avatar)(({ theme }) => ({
  marginRight: theme.spacing(1),
  width: theme.spacing(3),
  height: theme.spacing(3),
}));

const TimeStartContainer = styled(Typography)(({ theme }) => ({
  borderLeft: `1px solid ${theme.palette.grey['300']}`,
  paddingLeft: theme.spacing(2),
  paddingTop: theme.spacing(2),
  paddingBottom: theme.spacing(2),
  marginLeft: `-${theme.spacing(2)}`,
}));

const StyledTooltip = styled(({ className, ...props }: TooltipProps) => (
  <Tooltip {...props} componentsProps={{ tooltip: { className: className } }} />
))(`
    margin-bottom: 0 !important;
`);

const rowStyles = () => ({
  [`& td`]: {
    [`&:nth-of-type(1)`]: {
      width: 'calc(100% / 5)',
    },
    [`&:nth-of-type(2)`]: {
      width: 'calc(100% / 2.3)',
    },
    [`&:nth-of-type(3)`]: {
      width: 'calc(100% / 6)',
    },
    [`&:nth-of-type(4)`]: {
      width: 'calc(100% / 10)',
    },
    [`&:nth-of-type(5)`]: {
      width: 'calc(100% / 10)',
    },
  },
});

const bodyRowStyles = (theme: Theme) => ({
  cursor: 'pointer',
  [`&:hover`]: {
    [`& + tr`]: {
      [`& .MuiBox-root`]: {
        display: 'block',
      },
    },
    [`& td`]: {
      borderTop: '1px solid rgba(0, 169, 183, 0.5)',
      borderBottom: '1px solid rgba(0, 169, 183, 0.5)',
      [`&:nth-of-type(1)`]: {
        borderLeft: '1px solid rgba(0, 169, 183, 0.5)',
        borderTopLeftRadius: 8,
        borderBottomLeftRadius: 8,
      },
      [`&:nth-of-type(5)`]: {
        borderRight: '1px solid rgba(0, 169, 183, 0.5)',
        borderTopRightRadius: 8,
        borderBottomRightRadius: 8,
      },
      [`&:nth-of-type(6)`]: {
        display: 'flex',
        flexDirection: 'row-reverse',
        border: 0,
      },
    },
  },
  [`& td`]: {
    borderTop: '1px solid transparent',
    borderBottom: '1px solid transparent',
    [`&:nth-of-type(5)`]: {
      borderTopRightRadius: 8,
      borderBottomRightRadius: 8,
    },
    [`&:nth-of-type(6)`]: {
      position: 'absolute',
      right: theme.spacing(5),
      display: 'none',
      width: '200px',
      padding: 0,
    },
  },
});

const outcomeFilterData: OutcomeType[] = [
  OutcomeType.SUCCESS,
  OutcomeType.RUNNING,
  OutcomeType.FAILURE,
  OutcomeType.ABORTED,
  OutcomeType.NOT_AVAILABLE,
];

const ciStatus = (flag: null | boolean) => {
  if (flag === false) {
    return 'Desktop';
  }
  if (flag === true) {
    return 'CI';
  }
  return null;
};

const tabFilters: TableTabFilters = {
  myBuilds: {
    label: 'My Builds',
    value: {
      user: 'me',
    },
    noDataText: 'You haven’t run any builds yet',
  },
  myCiBuilds: {
    label: 'My CI Builds',
    value: {
      user: 'me',
      ci: 1,
    },
    noDataText: 'You have no CI builds in this repository',
  },
  myDesktopBuilds: {
    label: 'My Desktop Builds',
    value: {
      user: 'me',
      ci: 0,
    },
    noDataText: 'You have no desktop builds in this repository',
  },
  ciBuilds: {
    label: 'All CI Builds',
    value: {
      ci: 1,
    },
    noDataText: 'There are no CI builds in this repository',
  },
  allBuilds: {
    label: 'All Builds',
    value: {},
    noDataText: 'There are no builds in this repository',
  },
};

const getFilterTab = (query: QueryParams) => {
  const { ci, user } = query;

  if (user === 'me' && ci) {
    return 'myCiBuilds';
  }

  if (user === 'me' && ci === false) {
    return 'myDesktopBuilds';
  }

  if (user === 'me') {
    return 'myBuilds';
  }

  if (ci && user === undefined) {
    return 'ciBuilds';
  }

  return 'allBuilds';
};

const Goals = ({ build }: { build: Build }) => {
  const { goals } = build;
  const goalViewLimit = 3;

  const renderGoals = (goalsArray: string[]) => goalsArray.map(goal => <TextChip key={goal} text={goal} />);

  if (goals?.length <= goalViewLimit) {
    return <>{renderGoals(goals)}</>;
  }

  if (goals?.length > goalViewLimit) {
    const slicedGoals = goals.slice(0, goalViewLimit);
    const extraGoalsNumber = goals.length - slicedGoals.length;

    return (
      <Tooltip title={goals.join(', ')} placement="top-end" arrow>
        <Grid container alignItems="center">
          <Grid item>{renderGoals(slicedGoals)}</Grid>
          <Grid item>
            <Typography variant="body2">+{extraGoalsNumber}</Typography>
          </Grid>
        </Grid>
      </Tooltip>
    );
  }

  return null;
};

export const queryParamConfig = {
  page_size: NumberParam,
  sort: StringParam,
  earliest: StringParam,
  outcome: StringParam,
  branch: StringParam,
  user: StringParam,
  goals: ArrayParam,
  run_time_min: NumberParam,
  run_time_max: NumberParam,
  ci: BooleanParam,
  title: StringParam,
  pr: StringParam,
};

const ListBuildsPage = () => {
  const { repoSlug, orgSlug } = useParams();
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [query, updateQuery] = useQueryParams(queryParamConfig);
  const { user } = useUserContext();
  const [currentTab, setCurrentTab] = useState<string>(getFilterTab(query));
  const { setRepo, setOrg } = useOrgAndRepoContext();
  const { setErrorMessage } = useRequestErrorContext();
  const { setBuildParams } = useBuildsTableFiltersContext();
  const navigate = useNavigate();

  // When repo or org changes update the store
  useEffect(() => {
    setRepo(repoSlug);
    setOrg(orgSlug);
  }, [repoSlug, setRepo, setOrg, orgSlug]);

  // When query changes make sure to update current tab and filters store
  useEffect(() => {
    setCurrentTab(getFilterTab(query));
    setBuildParams(`${orgSlug}/${repoSlug}`, query);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  const tabFilterChange = (value: string) => {
    setCurrentTab(value);
    updateQuery(tabFilters[value].value, 'replace');
  };

  const [showError, toggleShowError] = useState(true);
  const buildQueryName = `${orgSlug}/${repoSlug}/${QueryNames.BUILDS}/${JSON.stringify(query)}`;

  const [{ data: orgsData, isFetching: isFetchingOrgs }] = useQueryGet<ApiListResponse<OrgList>>(
    [QueryNames.ORGS],
    backends.users_api.LIST_ORGANIZATIONS,
    null,
    { refetchOnMount: false }
  );

  const doesOrgBelongToUser = orgsData?.results.some(orgNode => orgNode.slug === orgSlug);

  const [{ data: reposData, isFetching: isFetchingRepos }] = useQueryGet<[OrgRepoList]>(
    [QueryNames.ALL_USER_REPOS],
    backends.users_api.LIST_ALL_REPOS,
    null,
    { enabled: !!orgSlug && !!doesOrgBelongToUser, refetchOnMount: false }
  );

  const doesRepoBelongToUser = reposData?.some(repoNode => repoNode.slug === repoSlug);

  const shouldRetryIndicators = true;
  const showRetrySnackbar = false;
  const [{ data: indicatorsData, isFetching: isFetchingIndicators }] = useQueryGet<{ indicators: BuildIndicators }>(
    [`${QueryNames.INDICATORS}-${orgSlug}-${repoSlug}/${JSON.stringify(query)}/${currentPage}`],
    backends.buildsense_api.RETRIEVE_INDICATORS(orgSlug, repoSlug),
    { ...query, page: currentPage },
    {
      enabled: !!repoSlug,
      initialData: { indicators: {} } as any,
      onError: error => {
        const err = Object.keys(error) ? new Error(JSON.stringify(error)) : error;

        captureException(err, {
          tags: { requestUrl: backends.buildsense_api.RETRIEVE_INDICATORS(orgSlug, repoSlug) },
        });
      },
    },
    shouldRetryIndicators,
    showRetrySnackbar
  );

  useEffect(() => {
    if ((orgsData && !doesOrgBelongToUser) || (reposData && !doesRepoBelongToUser)) {
      navigate('/404', { replace: true });
    }
  }, [orgsData, reposData, doesOrgBelongToUser, doesRepoBelongToUser, navigate]);

  const [buildsResponse] = useInfiniteQuery<BuildsListResponse>(
    [buildQueryName],
    backends.buildsense_api.LIST_BUILDS(orgSlug, repoSlug),
    query,
    {
      keepPreviousData: true,
      refetchOnWindowFocus: false,
      enabled: !!doesOrgBelongToUser && !!doesRepoBelongToUser,
    }
  );
  const [optionsResponse] = useQueryOptions<UsersOptionsResponse | UsersOptionsResponseNoBuilds>(
    [`${orgSlug}/${repoSlug}/${QueryNames.BUILDS_OPTIONS}`],
    backends.buildsense_api.LIST_BUILDS(orgSlug, repoSlug),
    {
      field: 'user_api_id,branch,goals,pr',
    },
    {
      enabled: !!doesOrgBelongToUser && !!doesRepoBelongToUser,
    }
  );

  const isLoading =
    (buildsResponse.isFetching && !buildsResponse.isFetchingNextPage && !buildsResponse.isFetchingPreviousPage) ||
    isFetchingOrgs ||
    isFetchingRepos;
  const errorMessage = buildsResponse.errorMessage || optionsResponse.errorMessage;
  const handleQueryChange: TableQueryChange = (type, values?) => {
    if (isRefreshing) {
      buildsResponse.abortQuery([buildQueryName]);
    }

    const formatRunTimeValue = (value: string) => {
      if (!value) {
        return undefined;
      }

      return (+value).toString();
    };

    if (type === 'reset') {
      // Filters have been reset, remove them from query.
      updateQuery({}, 'push');
    } else {
      const newQuery = {
        ...values,
      };

      if (values.run_time) {
        const minRunTime = formatRunTimeValue(values.run_time[0]);
        const maxRunTime = formatRunTimeValue(values.run_time[1]);

        newQuery.run_time_min = minRunTime !== '0' ? minRunTime : undefined;
        newQuery.run_time_max = maxRunTime !== '0' ? maxRunTime : undefined;

        delete newQuery.run_time;
      }

      if (values.earliest) {
        newQuery.earliest = relativeStringToUtcTime(values.earliest);
      }
      if (values.ci) {
        newQuery.ci = values.ci === 'CI';
      }
      updateQuery(newQuery, 'pushIn');
    }
  };

  const refreshBuildData = async () => {
    setIsRefreshing(true);
    await buildsResponse.refetch();
    setIsRefreshing(false);
  };

  // If slug changes while refreshing cancel query
  useEffect(() => {
    if (isRefreshing) {
      buildsResponse.abortQuery([buildQueryName]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repoSlug]);

  const { data, fetchNextPage, isFetchingNextPage } = buildsResponse;
  const results = data?.pages.some(a => a) && data.pages.reduce((acc, page) => [...acc, ...page.results], []);
  const tableData = useMemo<TableData<Build>>(
    () =>
      (results &&
        results.map(build => ({
          id: build.run_id,
          goals: build,
          context: build,
          user: build,
          started: build,
          duration: build,
        }))) ||
      null,
    [results]
  );

  useEffect(() => {
    if (data) setCurrentPage(data.pageParams.length);
  }, [data]);

  const renderUser = ({ full_name, avatar_url, username }: ToolchainUser) => {
    const hasFullName = !!full_name;
    return (
      <>
        <UserAvatar alt={full_name} src={avatar_url} />
        <Typography variant="body1" ml={1}>
          {hasFullName ? full_name : username}
        </Typography>
      </>
    );
  };

  const renderOutcomeAndGoalsCombined = (build: Build) => (
    <Grid container spacing={1}>
      <Grid item xs={12}>
        <BuildOutcome outcome={build.outcome} chipSize="small" chipVariant="border" />
      </Grid>
      <Grid item xs={12}>
        <Goals build={build} />
      </Grid>
    </Grid>
  );

  const tableColumns: TableColumns<Build> = {
    goals: {
      sortable: true,
      sortName: 'outcome',
      label: 'GOALS',
      renderValue: build => renderOutcomeAndGoalsCombined(build),
    },
    context: {
      sortable: false,
      sortName: null,
      label: 'CONTEXT',
      renderValue: ({ is_ci: isCi, ci_info: info, machine, title }: Build) =>
        isCi === true ? (
          <Grid container spacing={1}>
            {title ? (
              <Grid item xs={12}>
                {title}
              </Grid>
            ) : null}
            <Grid item xs={12}>
              {info.links.map(({ icon, text, link }) => (
                <ExternalLinkChip key={text} text={text} icon={icon} link={link} />
              ))}
            </Grid>
          </Grid>
        ) : (
          <>{machine}</>
        ),
    },
    user: {
      sortable: false,
      sortName: null,
      label: 'USER',
      renderValue: ({ user: rowUser }: Build) => (
        <AvatarChip text={rowUser.username} variant="filled" size="medium" avatar={rowUser.avatar_url} />
      ),
    },
    started: {
      sortable: true,
      sortName: 'timestamp',
      label: 'STARTED',
      renderValue: ({ datetime }) => (
        <StyledTooltip
          title={<Typography variant="caption">Started: {extendedDateTimeToLocal(datetime)}</Typography>}
          placement="top"
          arrow
        >
          <TimeStartContainer variant="body2">{utcTimeAgo(datetime)}</TimeStartContainer>
        </StyledTooltip>
      ),
    },
    duration: {
      sortable: true,
      sortName: 'run_time',
      label: 'DURATION',
      renderValue: ({ run_time }) => <Typography variant="body2">{run_time && durationToFormat(run_time)}</Typography>,
    },
  };

  const tableFilters: TableFilters = {
    since: {
      name: 'earliest',
      label: 'Since',
      noFilterValue: undefined,
      fullWidth: false,
      value: query.earliest ? utcTimeAgoToRelativeString(query.earliest) : undefined,
      options: ['1 hour ago', '1 day ago', '1 week ago'],
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
    branch: {
      name: 'branch',
      label: 'Branch',
      noFilterValue: undefined,
      fullWidth: false,
      value: query.branch ? query.branch : undefined,
      options: (optionsResponse.data as UsersOptionsResponse)?.branch?.values || [],
      filterRender: (value, onChange, name, label, options) => (
        <Autocomplete
          freeSolo
          multiple={false}
          options={options as string[]}
          value={value || ''}
          onChange={(event, newValue) => {
            const val = newValue ? (newValue as string) : undefined;

            onChange({ [name]: val });
          }}
          autoHighlight
          renderInput={params => (
            <TextField
              // eslint-disable-next-line react/jsx-props-no-spreading
              {...params}
              name={name}
              label={label}
              margin="none"
              onChange={event => {
                const newValue = event.target.value ? event.target.value : undefined;

                onChange({ [name]: newValue });
              }}
            />
          )}
        />
      ),
      chipRender: value => `Branch: '${value}'`,
    },
    goals: {
      name: 'goals',
      label: 'Goals',
      noFilterValue: undefined,
      fullWidth: false,
      value: query.goals ? query.goals : undefined,
      options: (optionsResponse.data as UsersOptionsResponse)?.goals?.values || [],
      filterRender: (value, onChange, name, label, options) => (
        <MultiSelectFilter
          fieldValue={value as string[]}
          onChange={onChange}
          fieldName={name}
          fieldLabel={label}
          options={options as string[]}
        />
      ),
      chipRender: value => `Goal: '${value}'`,
    },
    outcome: {
      name: 'outcome',
      label: 'Outcome',
      noFilterValue: undefined,
      fullWidth: false,
      value: query.outcome ? query.outcome : undefined,
      options: outcomeFilterData,
      filterRender: (value, onChange, name, label, options) => (
        <SelectFilter
          fieldValue={value as string}
          onChange={onChange}
          fieldName={name}
          fieldLabel={label}
          options={options as string[]}
        />
      ),
      chipRender: value => `Outcome: '${outcomeTexts[value as OutcomeType]}'`,
    },
    user: {
      name: 'user',
      label: 'User',
      noFilterValue: undefined,
      fullWidth: false,
      value: query.user ? query.user : undefined,
      options: (optionsResponse.data as UsersOptionsResponse)?.user_api_id?.values || [],
      filterRender: (value, onChange, name, label, options) => (
        <Autocomplete
          multiple={false}
          options={options as ToolchainUser[]}
          value={(options as ToolchainUser[])?.find(option => option.username === value) || null}
          onChange={(event: React.ChangeEvent<{}>, newValue) =>
            onChange({ [name]: (newValue as ToolchainUser)?.username })
          }
          autoHighlight
          getOptionLabel={option => (option as ToolchainUser).username}
          renderOption={(props, option: ToolchainUser) => <li {...props}>{renderUser(option)}</li>}
          renderInput={params => (
            <TextField
              // eslint-disable-next-line react/jsx-props-no-spreading
              {...params}
              name={name}
              label={label}
              margin="none"
              inputProps={{
                ...params.inputProps,
                'data-lpignore': 'true',
              }}
            />
          )}
        />
      ),
      chipRender: value =>
        `User ${
          (optionsResponse.data as UsersOptionsResponse)?.user_api_id?.values.find(item => item.username === value)
            ?.username ||
          user?.username ||
          'loading...'
        }`,
    },
    context: {
      name: 'ci',
      label: 'Build context',
      noFilterValue: undefined,
      fullWidth: false,
      value: query.ci === undefined ? undefined : ciStatus(query.ci),
      options: ['Desktop', 'CI'],
      filterRender: (value, onChange, name, label, options) => (
        <SelectFilter
          fieldValue={value as string}
          onChange={onChange}
          fieldName={name}
          fieldLabel={label}
          options={options as string[]}
        />
      ),
      chipRender: value => `${value}`,
    },
    pullRequest: {
      name: 'pr',
      label: 'Pull request',
      noFilterValue: undefined,
      fullWidth: false,
      value: query.pr ? query.pr : undefined,
      options: (optionsResponse.data as UsersOptionsResponse)?.pr?.values || [],
      filterRender: (value, onChange, name, label, options) => (
        <Autocomplete
          freeSolo
          multiple={false}
          options={options as number[]}
          value={(value as string) || null}
          onChange={(event, newValue) => {
            const val = newValue ? (newValue as string) : undefined;

            onChange({ [name]: val });
          }}
          autoHighlight
          getOptionLabel={option => option.toString()}
          renderInput={params => (
            <TextField
              // eslint-disable-next-line react/jsx-props-no-spreading
              {...params}
              name={name}
              label={label}
              margin="none"
              onChange={event => {
                const numbers = /^[0-9]+$/;
                const newValue =
                  event.target.value && event.target.value.match(numbers) ? event.target.value : undefined;

                onChange({ [name]: newValue });
              }}
            />
          )}
        />
      ),
      chipRender: value => `Pull request: #${value}`,
    },
    title: {
      name: 'title',
      label: 'Title',
      noFilterValue: undefined,
      fullWidth: false,
      value: query.title ? query.title : undefined,
      filterRender: (value, onChange, name, label) => (
        <PullRequestFilter fieldValue={value as string} onChange={onChange} fieldName={name} fieldLabel={label} />
      ),
      chipRender: value => `Title: ${value}`,
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
      value:
        query.run_time_max || query.run_time_min ? [query.run_time_min, query.run_time_max] : [undefined, undefined],
    },
  };

  const onRowClick = (e: React.MouseEvent<HTMLElement>, row: Build) => {
    const { run_id: runId, user: buildUser } = row;

    if (e.ctrlKey) {
      window.open(`organizations/${orgSlug}/repos/${repoSlug}/builds/${runId}/type/goal/`);
    } else {
      navigate(`${runId}/type/goal/`, {
        state: { user_api_id: buildUser.api_id },
      });
    }
  };

  const onOpenNewTabClick = (e: React.MouseEvent<HTMLElement>, row: Build) => {
    e.stopPropagation();
    const { run_id: runId } = row;

    window.open(paths.buildDetailsType(orgSlug, repoSlug, runId, 'goal'));
  };

  // Set sorting values for table
  const order: 'asc' | 'desc' | null = query?.sort && query.sort.charAt(0) === '-' ? 'desc' : 'asc' || null;
  const orderBy: string | null = query?.sort && query.sort.charAt(0) === '-' ? query.sort.slice(1) : query.sort || null;
  const sort = { order, orderBy };
  const totalPages = data?.pages[0].total_pages;
  const indicators = Object.keys(indicatorsData.indicators).length ? indicatorsData.indicators : null;
  const maxPaginationReached = currentPage === data?.pages[0].max_pages && currentPage < totalPages;
  const isLastPage = currentPage === totalPages || totalPages === 0 || maxPaginationReached;

  const fetchNextPageBuilds = () => {
    const page = (data.pageParams as (undefined | number)[])[data.pageParams.length - 1];
    const isFirstPage = data.pageParams.length === 1;
    const pageParam = (isFirstPage && 2) || page + 1;

    if (isFirstPage || !maxPaginationReached) fetchNextPage({ pageParam });
  };

  const pageTitle = repoSlug && repoSlug.charAt(0).toUpperCase() + repoSlug.slice(1);
  const { scm, repo_link: repoLink } = reposData?.find(
    repo => repo.slug === repoSlug && repo.customer_slug === orgSlug
  ) || {
    scm: '',
    repo_link: '',
  };

  const { results: orgResults } = orgsData || {};

  const org = orgResults?.find(organization => organization.slug === orgSlug);

  const { status, name } = org || {};

  const hasNoBuilds = (optionsResponse.data as UsersOptionsResponseNoBuilds)?.status === 'no_builds';
  const docsUrl = (optionsResponse.data as UsersOptionsResponseNoBuilds)?.docs;

  return (
    <Grid container spacing={4}>
      {status && (
        <Grid item xs={12}>
          <OrganizationBanner status={status} name={name} />
        </Grid>
      )}
      {hasNoBuilds && (
        <Grid item xs={12}>
          <OrganizationBanner status="noBuilds" name={name} docsUrl={docsUrl} />
        </Grid>
      )}
      <Grid item xs={12}>
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <BreadCrumbs org={orgSlug} />
          </Grid>
          <Grid item xs={12}>
            <Grid container spacing={2} alignItems="center">
              <Grid item>
                <Typography variant="h2">{pageTitle}</Typography>
              </Grid>
              <Grid item>
                <VisitScmButton url={repoLink} scm={scm} />
              </Grid>
            </Grid>
          </Grid>
        </Grid>
      </Grid>
      <Grid item xs={12}>
        <Table
          name="builds"
          columns={tableColumns}
          filters={tableFilters}
          data={tableData}
          sort={sort}
          currentTab={currentTab}
          tabFilters={tabFilters}
          isLoading={isLoading}
          isLoadingIndicators={isFetchingIndicators}
          onRowClick={onRowClick}
          onOpenNewTabClick={onOpenNewTabClick}
          onQueryChange={handleQueryChange}
          refreshData={refreshBuildData}
          setCurrentTab={tabFilterChange}
          fetchNext={fetchNextPageBuilds}
          isLoadingNext={isFetchingNextPage}
          isLastPage={isLastPage}
          maxPaginationReached={maxPaginationReached}
          rowStyles={rowStyles}
          bodyRowStyles={bodyRowStyles}
          // tableRowClass={classes.tableRow}
          // tableRowBodyClass={classes.tableBodyRow}
          indicators={indicators}
          showIndicators={true}
        />
        {showError && errorMessage && (
          <Snackbar
            anchorOrigin={{
              vertical: 'top',
              horizontal: 'center',
            }}
            open={showError}
            onClose={() => {
              toggleShowError(false);
              setErrorMessage(null);
            }}
            message={errorMessage}
          />
        )}
      </Grid>
    </Grid>
  );
};

export default ListBuildsPage;
