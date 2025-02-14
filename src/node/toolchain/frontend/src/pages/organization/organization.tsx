/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import Card from '@mui/material/Card';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import { useTheme } from '@mui/material/styles';
import useMediaQuery from '@mui/material/useMediaQuery';
import IconButton from '@mui/material/IconButton';
import Edit from '@mui/icons-material/Edit';
import Check from '@mui/icons-material/Check';
import Settings from '@mui/icons-material/Settings';
import DoneAll from '@mui/icons-material/DoneAll';
import FormControl from '@mui/material/FormControl';
import TextField from '@mui/material/TextField';
import Snackbar from '@mui/material/Snackbar';
import Close from '@mui/icons-material/Close';
import MuiAlert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import KeyIcon from '@mui/icons-material/Key';
import { styled } from '@mui/material/styles';

import backends from 'utils/backend-paths';
import { useOrgAndRepoContext } from 'store/org-repo-store';
import { useMutationPatch, useQueryGet } from 'utils/hooks/query';
import QueryNames from 'common/enums/QueryNames';
import { Organization, OrgList, Repo } from 'common/interfaces/orgs-repo';
import withLoadingAndError from 'utils/hoc/with-loading-and-error/with-loading-and-error';
import GithubInstall from 'components/github-install';
import OrganizationIcon from 'components/icons/organization-icon';
import VisitScmButton from 'components/visit-scm-button/visit-scm-button';
import { ApiListResponse } from 'common/interfaces/api';
import OrganizationBanner from 'components/organization-banner/organization-banner';
import CustomerStatus from 'common/enums/CustomerStatus';
import RepoCard from './repo-card/repo-card';
import OrganizationPlan from './organization-plan/organization-plan';
import paths from 'utils/paths';

type RepoListProps = {
  data?: { repos: Repo[]; install_link?: string; organizationStatus?: CustomerStatus };
  orgSlug: string;
  orgLogo: string;
  scm: string;
  customerLink: string;
  orgName: string;
  isAdmin: boolean;
  billingUrl?: string;
  isManagingRepos: boolean;
  setIsManagingRepos: (value: boolean) => void;
};
type OrgHeaderProps = Pick<
  RepoListProps,
  'orgLogo' | 'orgSlug' | 'scm' | 'customerLink' | 'isAdmin' | 'orgName' | 'billingUrl'
>;
type NoReposProps = { isAdmin: boolean };

const NoReposCard = styled(Card)(({ theme }) => ({
  width: '100%',
  marginTop: theme.spacing(3),
  borderRadius: theme.spacing(1),
  backgroundColor: theme.palette.grey[50],
  padding: theme.spacing(10),
  [theme.breakpoints.down('sm')]: {
    padding: theme.spacing(5),
  },
}));

const NoReposText = styled(Typography)(({ theme }) => ({
  color: theme.palette.text.disabled,
  textAlign: 'center',
}));

const NoReposContainer = styled(Grid)(() => ({
  minHeight: '90vh',
}));

const StyledTextField = styled(TextField)(() => ({
  '& .MuiInput-underline': {
    '&:before': {
      borderBottom: 'none !important',
    },
    '&:after': {
      borderBottom: 'none !important',
    },
    '&:hover': {
      borderBottom: 'none !important',
    },
  },
}));

const WorkerTokensButton = styled(Button)(({ theme }) => ({
  backgroundColor: 'rgba(0, 169, 183, 0.08)',
  borderRadius: theme.spacing(5),
  padding: `${theme.spacing(1)} ${theme.spacing(3)}`,
  border: '1px solid transparent',
  boxShadow: 'none',
  '&:hover': {
    backgroundColor: 'rgba(0, 169, 183, 0.08)',
    border: '1px solid rgba(0, 169, 183, 0.5)',
  },
}));

const StyledKeyIcon = styled(KeyIcon)(({ theme }) => ({
  color: theme.palette.primary.dark,
}));

const OrgHeader = ({ orgSlug, orgLogo, scm, customerLink, isAdmin, orgName }: OrgHeaderProps) => {
  const [isEditing, setIsEditing] = useState(false);
  const [openError, setOpenError] = useState(false);
  const [name, setName] = useState(orgName);
  const [nameError, setNameError] = useState(null);
  const queryClient = useQueryClient();
  const theme = useTheme();
  const navigate = useNavigate();

  const MIN_ORG_NAME_LENGTH = 2;
  const MAX_ORG_NAME_LENGTH = 128;

  const matchesMobile = useMediaQuery(theme.breakpoints.down('md'));

  const gridJustify = matchesMobile ? 'center' : 'flex-start';
  const orgHeaderDirection = matchesMobile ? 'column' : 'row';
  const descriptionAlign = matchesMobile ? 'center' : 'flex-start';

  const [{ isLoading, mutate }] = useMutationPatch(
    [QueryNames.EDIT_ORG],
    backends.users_api.ORGANIZATION(orgSlug),
    JSON.stringify({
      name,
    }),
    {
      onError: (error: any) => {
        if (error.error?.errors?.name) {
          setNameError(error.error.errors.name.map((err: { message: string; code: string }) => err.message).join(' '));
        } else {
          setOpenError(true);
        }
      },
      onSuccess: () => {
        queryClient.invalidateQueries([QueryNames.ORGS]);
        setNameError(null);
        setIsEditing(false);
      },
    },
    true
  );

  const submitNameForm = () => mutate({});
  const startEdit = () => {
    setIsEditing(true);
  };
  const handleNameChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { value } = event.target;
    const trimmedValue = value.trim();

    if (!trimmedValue) {
      setNameError('Organization name is required.');
    } else if (trimmedValue.length < MIN_ORG_NAME_LENGTH) {
      setNameError(`Organization name must be at least ${MIN_ORG_NAME_LENGTH} characters long.`);
    } else if (trimmedValue.length > MAX_ORG_NAME_LENGTH) {
      setNameError(`Organization name can't be more than ${MAX_ORG_NAME_LENGTH} characters long.`);
    } else {
      setNameError(false);
    }

    if (value !== name) {
      setIsEditing(true);
      setName(value);
    }
  };

  const hasError = !!nameError;
  const isDisabled = hasError || orgName === name;

  return (
    <Grid container justifyContent="space-between" alignItems="center">
      <Grid item>
        <Grid container justifyContent={gridJustify} alignItems="center" spacing={3} direction={orgHeaderDirection}>
          <Grid item>
            <OrganizationIcon slug={orgSlug} url={orgLogo} size="large" />
          </Grid>
          <Grid item>
            <Grid container direction="column" alignItems={descriptionAlign}>
              <Grid item xs={5}>
                {isEditing ? (
                  <Grid container spacing={2} alignItems="center">
                    <Grid item>
                      <FormControl>
                        <StyledTextField
                          id="org-name-input"
                          aria-describedby="org-name-text"
                          error={hasError}
                          helperText={nameError}
                          defaultValue={name}
                          onChange={handleNameChange}
                          inputProps={{
                            'aria-label': 'org-name',
                            style: { fontSize: 48 },
                          }}
                          autoFocus
                          disabled={isLoading}
                          name="org-name"
                          autoComplete="off"
                          type="text"
                        />
                      </FormControl>
                    </Grid>
                    <Grid item>
                      <IconButton
                        aria-label="save org name"
                        onClick={submitNameForm}
                        size="large"
                        disabled={isDisabled}
                      >
                        <Check color={isDisabled ? 'disabled' : 'primary'} />
                      </IconButton>
                    </Grid>
                  </Grid>
                ) : (
                  <Grid container spacing={2} alignItems="center">
                    <Grid item>
                      <Typography variant="h1">{name}</Typography>
                    </Grid>
                    {isAdmin ? (
                      <Grid item>
                        <IconButton aria-label="edit org name" onClick={() => startEdit()} size="large">
                          <Edit color="primary" />
                        </IconButton>
                      </Grid>
                    ) : null}
                  </Grid>
                )}
              </Grid>
              <Grid item>
                <VisitScmButton url={customerLink} scm={scm} />
              </Grid>
            </Grid>
          </Grid>
        </Grid>
      </Grid>
      <Grid item>
        <WorkerTokensButton
          variant="contained"
          startIcon={<StyledKeyIcon />}
          onClick={() => navigate(paths.workerTokens(orgSlug))}
          disableElevation={true}
        >
          <Typography variant="body1" textTransform="none" color="primary.dark">
            Worker tokens
          </Typography>
        </WorkerTokensButton>
      </Grid>
      <Snackbar
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        autoHideDuration={5000}
        open={openError}
        onClose={() => setOpenError(false)}
      >
        <MuiAlert
          icon={false}
          severity="error"
          variant="filled"
          onClose={() => setOpenError(false)}
          action={
            <IconButton size="small" aria-label="close" color="inherit" onClick={() => setOpenError(false)}>
              <Close />
            </IconButton>
          }
        >
          Something wrong happened, please try again
        </MuiAlert>
      </Snackbar>
    </Grid>
  );
};

const NoRepos = ({ isAdmin }: NoReposProps) => {
  const text = isAdmin
    ? 'There are no repos in your GitHub org.'
    : 'There are no repos in this organization. Please contact the admin to configure it.';
  return (
    <NoReposCard elevation={0}>
      <NoReposText variant="h3">{text}</NoReposText>
    </NoReposCard>
  );
};

const RepoList = ({
  data,
  orgSlug,
  orgLogo,
  scm,
  customerLink,
  isAdmin,
  orgName,
  billingUrl,
  isManagingRepos,
  setIsManagingRepos,
}: RepoListProps) => {
  const { repos, install_link: installLink, organizationStatus } = data;

  const hasRepos = repos?.length;
  const { setOrg, setRepo } = useOrgAndRepoContext();
  const theme = useTheme();

  const matchesMobile = useMediaQuery(theme.breakpoints.down('md'));

  const reposPaddingIndex = matchesMobile ? 2 : 3;

  const manageButtonIcon = isManagingRepos ? <DoneAll /> : <Settings />;
  const manageButtonText = isManagingRepos ? 'DONE' : 'MANAGE REPOS';

  // Update organization in the store on change
  useEffect(() => setOrg(orgSlug), [orgSlug, setOrg]);

  // Reset repo on repo list load
  useEffect(() => setRepo(null));

  if (!hasRepos && installLink) {
    return (
      <NoReposContainer container direction="column" spacing={0} alignItems="center" justifyContent="center">
        <Grid item>
          <GithubInstall installLink={installLink} />
        </Grid>
      </NoReposContainer>
    );
  }

  return (
    <Grid container spacing={5}>
      {organizationStatus && (
        <Grid item xs={12}>
          <OrganizationBanner status={organizationStatus} name={orgName} />
        </Grid>
      )}
      <Grid item xs={12}>
        <OrgHeader
          orgSlug={orgSlug}
          orgLogo={orgLogo}
          scm={scm}
          customerLink={customerLink}
          isAdmin={isAdmin}
          orgName={orgName}
          billingUrl={billingUrl}
        />
      </Grid>
      <Grid item xs={12}>
        <OrganizationPlan billingUrl={billingUrl} orgSlug={orgSlug} />
      </Grid>
      <Grid item xs={12}>
        <Grid container spacing={reposPaddingIndex}>
          <Grid item xs={12}>
            <Grid container justifyContent="space-between" alignItems="center">
              <Grid item>
                <Typography variant="h2">Repositories</Typography>
              </Grid>
              {isAdmin ? (
                <Grid item>
                  <Button
                    variant="outlined"
                    color="primary"
                    startIcon={manageButtonIcon}
                    onClick={() => setIsManagingRepos(!isManagingRepos)}
                  >
                    <Typography variant="button1" color="primary">
                      {manageButtonText}
                    </Typography>
                  </Button>
                </Grid>
              ) : null}
            </Grid>
          </Grid>
          <Grid item xs={12}>
            <Grid aria-label="Repositories" container spacing={reposPaddingIndex}>
              {hasRepos ? (
                repos?.map(({ id, name, slug, is_active: isActive }) => (
                  <RepoCard
                    key={id}
                    name={name}
                    slug={slug}
                    isActive={isActive}
                    orgSlug={orgSlug}
                    isManagingRepos={isManagingRepos}
                    isAdmin={isAdmin}
                  />
                ))
              ) : (
                <NoRepos isAdmin={isAdmin} />
              )}
            </Grid>
          </Grid>
        </Grid>
      </Grid>
    </Grid>
  );
};

const OrganizationPage = () => {
  const { orgSlug } = useParams();
  const [isManagingRepos, setIsManagingRepos] = useState(false);
  const navigate = useNavigate();

  const [{ data: orgData, isFetching: isFetchingOrgData }] = useQueryGet<ApiListResponse<OrgList>>(
    [QueryNames.ORGS],
    backends.users_api.LIST_ORGANIZATIONS,
    null,
    { refetchOnMount: false }
  );

  const [{ data, isFetching, errorMessage }] = useQueryGet<Organization>(
    [`${QueryNames.ORG}/${orgSlug}`],
    backends.users_api.ORGANIZATION(orgSlug),
    null,
    {
      enabled: !!orgSlug,
      onError: (error: any) => {
        if (error.retryProps.status === 404) {
          navigate('/404', { replace: true });
        } else {
          return error;
        }
      },
    }
  );

  const { customer, metadata, repos, user } = data || {};

  const { scm, logo_url: orgLogo, customer_link: customerLink, billing } = customer || {};

  const { is_admin: isAdmin } = user || {};

  const { results } = orgData || {};

  const organizationStatus = results?.find(organization => organization.slug === orgSlug)?.status;

  const organizationName = results?.find(organization => organization.slug === orgSlug)?.name;

  const effectiveData = { repos, organizationStatus, ...metadata };

  const loading = isFetching || isFetchingOrgData;

  const RepoComponent = withLoadingAndError(RepoList, effectiveData, loading, errorMessage);

  return (
    <RepoComponent
      orgSlug={orgSlug}
      orgLogo={orgLogo}
      scm={scm}
      customerLink={customerLink}
      isAdmin={isAdmin}
      billingUrl={billing}
      orgName={organizationName}
      isManagingRepos={isManagingRepos}
      setIsManagingRepos={setIsManagingRepos}
    />
  );
};

export default OrganizationPage;
