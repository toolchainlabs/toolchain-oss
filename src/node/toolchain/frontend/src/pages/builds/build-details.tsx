/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useEffect, useState, useRef } from 'react';
import { useLocation, useParams, Route, Routes, Link, useNavigate } from 'react-router-dom';
import Grid from '@mui/material/Grid';
import Tab from '@mui/material/Tab';
import TabContext from '@mui/lab/TabContext';
import Tabs from '@mui/material/Tabs';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useQueryParams, StringParam, NumberParam } from 'use-query-params';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import Typography from '@mui/material/Typography';
import ArrowBack from '@mui/icons-material/ArrowBack';
import CloudDownloadIcon from '@mui/icons-material/CloudDownload';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import { styled } from '@mui/material/styles';

import withLoadingAndError from 'utils/hoc/with-loading-and-error/with-loading-and-error';
import BreadCrumbs from 'components/breadrumbs/breadcrumbs';
import { BuildArtifacts, BuildResponse, DownloadLink } from 'common/interfaces/builds';
import paths from 'utils/paths';
import backends from 'utils/backend-paths';
import { useQueryGet } from 'utils/hooks/query';
import { BuildArtifact } from 'common/interfaces/build-artifacts';
import OutcomeType from 'common/enums/OutcomeType';
import { BuildOutcome, OutcomeIcon } from 'components/icons/build-outcome';
import CacheIndicators from 'components/cache-indicators/cache-indicators';
import { useBuildsTableFiltersContext } from 'store/builds-filters-store';
import { useOrgAndRepoContext } from 'store/org-repo-store';
import Artifact, { artifactsContainValidContentType } from './artifact';
import Details from './details-pane';
import NoBuildDetailsData from './no-build-details-data';
import { durationToFormat } from 'utils/datetime-formats';
import downloadFile from 'utils/download-file';
import { ApiListResponse } from 'common/interfaces/api';
import { OrgList } from 'common/interfaces/orgs-repo';
import QueryNames from 'common/enums/QueryNames';
import OrganizationBanner from 'components/organization-banner/organization-banner';

const StyledTabs = styled(Tabs)(({ theme }) => ({
  [`& .MuiTabs-indicator`]: {
    display: 'flex',
    justifyContent: 'center',
    backgroundColor: 'transparent',
    height: 'unset',
    [`& span`]: { border: `2px solid ${theme.palette.primary.main}`, width: 20, borderRadius: theme.spacing(2) },
  },
}));

const StyledTab = styled(Tab)(({ theme }) => ({
  minWidth: 'unset',
  padding: `${theme.spacing(1)} 0 ${theme.spacing(2)} 0`,
  marginRight: theme.spacing(5),
  textTransform: 'none',
  textDecoration: 'none',
  [`&:hover`]: {
    textDecoration: 'none',
  },
  [`&.Mui-selected`]: {
    color: theme.palette.text.primary,
  },
})) as unknown as typeof Tab;

const StyledSubTabs = styled(Tabs)(({ theme }) => ({
  [`& .MuiTabs-flexContainer`]: {
    maxWidth: 'fit-content',
    alignItems: 'flex-end',
    backgroundColor: theme.palette.common.white,
    border: `1px solid transparent`,
    borderRadius: 10,
    padding: `0 ${theme.spacing(1)}`,
    marginBottom: theme.spacing(3),
  },
  [`& .MuiTabs-indicator`]: {
    display: 'flex',
    justifyContent: 'center',
    backgroundColor: 'transparent',
    height: 'unset',
    marginBottom: 2,
    bottom: 22,
    [`& span`]: { border: `1px solid ${theme.palette.primary.main}`, width: 27 },
  },
}));

const StyledSubTab = styled(Tab)(({ theme }) => ({
  padding: 0,
  minWidth: 'unset',
  minHeight: 'unset',
  margin: `10px ${theme.spacing(2)} 10px ${theme.spacing(2)}`,
  [`&.Mui-selected`]: {
    color: theme.palette.primary.main,
  },
})) as unknown as typeof Tab;

const StyledDownloadIconButton = styled(IconButton)(() => ({
  cursor: 'pointer',
  zIndex: 1301,
  [`&:hover`]: {
    background: 'rgba(0, 169, 183, 0.08)',
  },
}));

type ArtifactsByType = { [key: string]: BuildArtifacts };
type ArtifactsProps = { artifacts: BuildArtifacts };
type TabPanelProps = {
  children?: React.ReactNode;
  index: string;
  value: string;
};
type DownloadItemProps = {
  name: string;
  link: string;
  runId: string;
  onDownloadClick: (fetchMethod: () => any, fileName: string) => void;
};
type DownloadMenuProps = Pick<DownloadItemProps, 'runId'> & { downloadLinks: DownloadLink[] };

const TabPanel = ({ children, value, index, ...other }: TabPanelProps) => (
  <div
    role="tabpanel"
    hidden={value !== index}
    id={`artifact-tabpanel-${index}`}
    aria-labelledby={`artifact-tab-${index}`}
    // eslint-disable-next-line react/jsx-props-no-spreading
    {...other}
  >
    {value === index && children}
  </div>
);

const getArtifactOutcome = (outcomeStr?: string): OutcomeType => {
  if (!outcomeStr) {
    return OutcomeType.NOT_AVAILABLE;
  }
  return outcomeStr === 'FAILURE' ? OutcomeType.FAILURE : OutcomeType.SUCCESS;
};

const sortArtifactsByType = (artifacts: BuildArtifacts): ArtifactsByType => {
  const goalAndRunArtifacts = Object.keys(artifacts).reduce(
    (acc, key) => ({
      ...acc,
      [artifacts[key].type]: {
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        ...Object.fromEntries(
          Object.entries(artifacts).filter(
            ([aKey, value]) => artifacts[key].type === value.type && aKey !== 'targets_specs'
          )
        ),
      },
    }),
    {}
  );

  const targetArtifact = {
    targets: {
      ...Object.fromEntries(
        Object.entries(artifacts).filter(
          ([key, value]) => artifacts[key].type === value.type && key === 'targets_specs'
        )
      ),
    },
  };

  if (Object.keys(targetArtifact.targets).length === 0) {
    return goalAndRunArtifacts;
  }

  return { ...goalAndRunArtifacts, ...targetArtifact };
};

type BuildDetailsProps = {
  data?: BuildResponse;
};

const BuildDetails = ({ data }: BuildDetailsProps) => {
  const { repoSlug, runId, orgSlug } = useParams();
  const location = useLocation();
  const { state, pathname } = location as { pathname: string; state: { user_api_id: string } };
  const [query, updateQuery] = useQueryParams({
    subTab: StringParam,
    testTab: StringParam,
    firstLine: NumberParam,
    lastLine: NumberParam,
  });
  const { setRepo, setOrg } = useOrgAndRepoContext();
  const { run_info: runInfo } = data;
  const artifactsByType = sortArtifactsByType(runInfo.build_artifacts);
  const navigate = useNavigate();

  // When repo or org changes update the store
  useEffect(() => {
    setRepo(repoSlug);
    setOrg(orgSlug);
  }, [repoSlug, setRepo, setOrg, orgSlug]);

  const NavigationTabs = () => (
    <StyledTabs value={pathname} variant="scrollable" scrollButtons="auto" TabIndicatorProps={{ children: <span /> }}>
      <StyledTab
        disableRipple
        label={<Typography variant="h3">Outputs</Typography>}
        value={paths.buildDetailsType(orgSlug, repoSlug, runId, 'goal')}
        title="Outputs"
        component={Link}
        to={paths.buildDetailsType(orgSlug, repoSlug, runId, 'goal')}
      />
      <StyledTab
        disableRipple
        label={<Typography variant="h3">Targets</Typography>}
        value={paths.buildDetailsType(orgSlug, repoSlug, runId, 'targets')}
        title="Targets"
        component={Link}
        to={paths.buildDetailsType(orgSlug, repoSlug, runId, 'targets')}
      />
      <StyledTab
        disableRipple
        label={<Typography variant="h3">Details</Typography>}
        value={paths.buildDetailsType(orgSlug, repoSlug, runId, 'run')}
        title="Details"
        component={Link}
        to={paths.buildDetailsType(orgSlug, repoSlug, runId, 'run')}
      />
    </StyledTabs>
  );

  const TestArtifact = ({ artifacts }: { artifacts: BuildArtifact[] }) => {
    const sortedTestArtifacts: { [key: string]: BuildArtifact[] } = artifacts.reduce((acc, artifact) => {
      const contentType = artifact.content_types[0];
      const titleToContentTypeMap: { [key: string]: string } = {
        coverage_summary: 'CODE COVERAGE',
        'text/plain': 'CONSOLE OUTPUT',
        'pytest_results/v2': 'RESULTS',
      };

      return {
        ...acc,
        [titleToContentTypeMap[contentType]]: artifacts.filter(testArtifact =>
          testArtifact.content_types.includes(contentType)
        ),
      };
    }, {});
    const testTabValue = query.testTab || Object.keys(sortedTestArtifacts)[0];

    useEffect(() => {
      if (!query.testTab) {
        navigate(
          { pathname, search: `?subTab=${query.subTab}&testTab=${testTabValue}` },
          {
            replace: true,
            state: { ...state },
          }
        );
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return (
      <TabContext value={testTabValue}>
        <StyledSubTabs
          value={testTabValue}
          onChange={(event, value) => {
            if (value !== query.testTab) {
              updateQuery({ ...query, testTab: value });
            }
          }}
          TabIndicatorProps={{ children: <span /> }}
        >
          {Object.keys(sortedTestArtifacts).map(key => {
            const shouldRender = sortedTestArtifacts[key].length > 0;

            const icon = sortedTestArtifacts[key].some(
              artifact => artifact.result && artifact.result === OutcomeType.FAILURE
            ) ? (
              <OutcomeIcon outcome={OutcomeType.FAILURE} />
            ) : null;

            return shouldRender && <StyledSubTab key={key} label={key} value={key} title={key} icon={icon} />;
          })}
        </StyledSubTabs>
        {Object.keys(sortedTestArtifacts).map(key => (
          <TabPanel key={key} value={testTabValue} index={key}>
            {sortedTestArtifacts[key].map(({ name, result, description }) => (
              <Artifact
                key={name}
                artifactId={name}
                outcome={getArtifactOutcome(result)}
                artifactDescription={description}
              />
            ))}
          </TabPanel>
        ))}
      </TabContext>
    );
  };

  const Artifacts = ({ artifacts }: ArtifactsProps) => {
    const hasNoSubTabMatch = !!artifacts
      ? Object.keys(artifacts).includes(query.subTab)
      : query.subTab || Object.keys(artifacts)[0];
    const subTabValue = (hasNoSubTabMatch && query.subTab) || Object.keys(artifacts)[0];
    const allArtifacts = Object.keys(artifacts).reduce((acc, key) => [...acc, ...artifacts[key].artifacts], []);

    useEffect(() => {
      // If no subTab is present
      if (!hasNoSubTabMatch) {
        navigate(
          {
            pathname,
            search: `?subTab=${subTabValue}`,
          },
          {
            replace: true,
            state: { ...state },
          }
        );
      }
    }, [subTabValue, hasNoSubTabMatch]);

    const noArtifactsMessage =
      artifacts[subTabValue]?.type === 'goal' ? (
        <NoBuildDetailsData message="There are no outputs in this build" />
      ) : (
        <NoBuildDetailsData message="There are no details in this build" />
      );
    const shouldRenderTabs = artifactsContainValidContentType(allArtifacts);

    useEffect(() => {
      if (!query.subTab) {
        navigate(
          { pathname, search: `?subTab=${subTabValue}` },
          {
            replace: true,
            state: { ...state },
          }
        );
      }
    });

    if (artifacts.targets_specs) {
      return (
        <>
          {artifacts.targets_specs.artifacts.map(({ name, description, result }) => (
            <Artifact
              key={name}
              artifactId={name}
              outcome={getArtifactOutcome(result)}
              artifactDescription={description}
            />
          ))}
        </>
      );
    }

    return shouldRenderTabs ? (
      <TabContext value={subTabValue}>
        <StyledSubTabs
          value={subTabValue}
          onChange={(event, value) => {
            if (value !== query.subTab) {
              updateQuery({ subTab: value, testTab: undefined, firstLine: undefined, lastLine: undefined });
            }
          }}
          TabIndicatorProps={{ children: <span /> }}
        >
          {Object.keys(artifacts).map(key => {
            const shouldRender = artifactsContainValidContentType(artifacts[key].artifacts);
            const tabDisplayName = artifacts[key].name || key;
            return (
              shouldRender && (
                <StyledSubTab
                  key={key}
                  label={tabDisplayName}
                  value={key}
                  title={key}
                  icon={
                    (artifacts[key].artifacts.some(artifact => artifact.result === OutcomeType.FAILURE) && (
                      <OutcomeIcon outcome={OutcomeType.FAILURE} />
                    )) ||
                    null
                  }
                />
              )
            );
          })}
        </StyledSubTabs>
        {Object.keys(artifacts).map(key => {
          const isTest = key === 'test';

          return isTest ? (
            <TabPanel key={key} value={subTabValue} index={key}>
              <TestArtifact key={key} artifacts={artifacts[key].artifacts} />
            </TabPanel>
          ) : (
            <TabPanel key={key} value={subTabValue} index={key}>
              {artifacts[key].artifacts.map(({ name, description, result }) => (
                <Artifact
                  key={name}
                  artifactId={name}
                  outcome={getArtifactOutcome(result)}
                  artifactDescription={description}
                />
              ))}
            </TabPanel>
          );
        })}
      </TabContext>
    ) : (
      noArtifactsMessage
    );
  };

  return (
    <Grid container spacing={3}>
      <Grid item xs={12}>
        {runInfo && <Details data={runInfo} />}
      </Grid>
      <Grid item xs={12}>
        <NavigationTabs />
      </Grid>
      <Grid item xs={12}>
        <Routes>
          {Object.keys(artifactsByType).map((key: string) => (
            <Route key={key} path={`type/${key}/`} element={<Artifacts artifacts={artifactsByType[key]} />} />
          ))}
          {!Object.keys(artifactsByType).includes('goal') && (
            <Route path="type/goal/" element={<NoBuildDetailsData message="There are no outputs in this build" />} />
          )}
          {!Object.keys(artifactsByType).includes('targets') && (
            <Route path="type/targets/" element={<NoBuildDetailsData message="There are no targets in this build" />} />
          )}
          {!Object.keys(artifactsByType).includes('run') && (
            <Route path="type/run/" element={<NoBuildDetailsData message="There are no details in this build" />} />
          )}
        </Routes>
      </Grid>
    </Grid>
  );
};

const DownloadItem = ({ name, link, runId, onDownloadClick }: DownloadItemProps) => {
  const fileName = `${runId}-${name}.json`;
  const [{ isFetching, refetch }] = useQueryGet<any>([fileName], link, null, { enabled: false });

  return (
    <MenuItem onClick={() => onDownloadClick(refetch, fileName)} disabled={isFetching}>
      <Typography variant="button">{name}</Typography>
    </MenuItem>
  );
};

const DownloadMenu = ({ runId, downloadLinks }: DownloadMenuProps) => {
  const [anchorEl, setAnchorEl] = useState(null);
  const menuRef = useRef(null);

  const showDownloadMenu = (event: React.MouseEvent<HTMLButtonElement>) => {
    if (anchorEl !== event.currentTarget) {
      setAnchorEl(event.currentTarget);
    }
  };

  const hideDownloadMenu = (event: React.MouseEvent<HTMLButtonElement | HTMLUListElement>) => {
    if (event.currentTarget.localName !== 'ul') {
      const menu = menuRef.current.children[2] as HTMLElement;

      const menuBoundary = {
        left: event.currentTarget.offsetLeft + event.currentTarget.offsetWidth,
        top: menu.offsetTop,
        right: menu.offsetLeft + menu.offsetWidth,
        bottom: menu.offsetTop + menu.offsetWidth,
      };
      if (
        event.clientX >= menuBoundary.left &&
        event.clientX <= menuBoundary.right &&
        event.clientY <= menuBoundary.bottom &&
        event.clientY >= menuBoundary.top
      ) {
        return;
      }
    }
    setAnchorEl(null);
  };

  const onDownloadClick = async (fetchMethod: () => any, name: string) => {
    const { data: fileData } = await fetchMethod();

    if (fileData) {
      const string = JSON.stringify(fileData);
      const bytes = new TextEncoder().encode(string);
      downloadFile(bytes, name);
    }
  };

  return (
    <>
      <StyledDownloadIconButton
        aria-label="Download files"
        size="large"
        onMouseOver={showDownloadMenu}
        onMouseLeave={hideDownloadMenu}
        aria-owns={Boolean(anchorEl) ? 'file-download-menu' : null}
        aria-haspopup="true"
      >
        <CloudDownloadIcon color="primary" />
      </StyledDownloadIconButton>
      <Menu
        id="file-download-menu"
        ref={menuRef}
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'bottom',
          horizontal: 'left',
        }}
        MenuListProps={{
          onMouseLeave: hideDownloadMenu,
        }}
      >
        {downloadLinks.map(({ name, link }) => (
          <DownloadItem key={name} name={name} link={link} runId={runId} onDownloadClick={onDownloadClick} />
        ))}
      </Menu>
    </>
  );
};

const BuildDetailsPage = () => {
  const { repoSlug, orgSlug, runId } = useParams();
  const location = useLocation();
  const { state } = location as { state: { user_api_id: string } };
  const { buildParams } = useBuildsTableFiltersContext();
  const queryParams = buildParams[`${orgSlug}/${repoSlug}`] || '';
  const navigate = useNavigate();

  const [{ data: buildData, isFetching, errorMessage, refetch }] = useQueryGet<BuildResponse>(
    [runId],
    backends.buildsense_api.RETRIEVE_BUILD(orgSlug, repoSlug, runId),
    { ...state }
  );
  const [{ data: orgData, isFetching: isFetchingOrgData }] = useQueryGet<ApiListResponse<OrgList>>(
    [QueryNames.ORGS],
    backends.users_api.LIST_ORGANIZATIONS,
    null,
    { refetchOnMount: false }
  );

  const isLoading = isFetching || isFetchingOrgData;

  const downloadLinks = buildData?.run_info.download_links;
  const hasDownloadLinks = downloadLinks?.length;

  const DetailsComponent = withLoadingAndError(BuildDetails, buildData, isLoading, errorMessage);

  const hasIndication = buildData?.run_info.indicators;
  const runTime = buildData?.run_info.run_time;

  const refreshOrIndicate = hasIndication ? (
    <CacheIndicators indicators={buildData?.run_info.indicators} loading={false} />
  ) : (
    <Button variant="contained" color="primary" onClick={() => refetch()} startIcon={<RefreshIcon fontSize="small" />}>
      <Typography variant="button">REFRESH</Typography>
    </Button>
  );

  const { results } = orgData || {};

  const org = results?.find(organization => organization.slug === orgSlug);

  const { status, name: orgName } = org || {};

  return (
    <Grid container spacing={5}>
      {status && (
        <Grid item xs={12}>
          <OrganizationBanner status={status} name={orgName} />
        </Grid>
      )}
      <Grid item xs={12}>
        <Grid container justifyContent="space-between" alignItems="center" spacing={1}>
          <Grid item xs={12}>
            <BreadCrumbs org={orgSlug} repo={repoSlug} />
          </Grid>
          <Grid item xs={12}>
            <Button
              variant="text"
              onClick={() => navigate({ pathname: paths.builds(orgSlug, repoSlug), search: queryParams })}
              startIcon={<ArrowBack fontSize="small" color="primary" />}
            >
              <Typography variant="button2" color="primary">
                GO BACK
              </Typography>
            </Button>
          </Grid>
          <Grid item xs={12} sm="auto">
            <Grid container alignItems="center" spacing={3}>
              <Grid item>
                <Typography variant="h2">Build</Typography>
              </Grid>
              <Grid item>{buildData && <BuildOutcome outcome={buildData.run_info.outcome} />}</Grid>
              {hasDownloadLinks ? (
                <Grid item>
                  <DownloadMenu runId={runId} downloadLinks={downloadLinks} />
                </Grid>
              ) : null}
            </Grid>
          </Grid>
          <Grid item xs={12} sm="auto">
            <Grid container spacing={2} alignItems="center">
              {!!runTime && (
                <Grid item>
                  <Typography variant="subtitle1" color="primary.dark">
                    {durationToFormat(runTime)}
                  </Typography>
                </Grid>
              )}
              <Grid item>{refreshOrIndicate}</Grid>
            </Grid>
          </Grid>
        </Grid>
      </Grid>
      <Grid item xs={12}>
        <DetailsComponent />
      </Grid>
    </Grid>
  );
};

export default BuildDetailsPage;
