/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import Card from '@mui/material/Card';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import CloseIcon from '@mui/icons-material/Close';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import IconButton from '@mui/material/IconButton';
import Snackbar from '@mui/material/Snackbar';
import Alert from '@mui/material/Alert';

import paths from 'utils/paths';
import QueryNames from 'common/enums/QueryNames';
import { useMutationDelete, useMutationPost } from 'utils/hooks/query';
import backendPaths from 'utils/backend-paths';
import { Organization, Repo } from 'common/interfaces/orgs-repo';
import { styled } from '@mui/material/styles';

type RepoCardProps = {
  name: string;
  slug: string;
  isActive: boolean;
  orgSlug: string;
  isManagingRepos: boolean;
  isAdmin: boolean;
};
type RepoDialogProps = {
  open: boolean;
  close: () => void;
  repo: { name: string; slug: string; orgSlug: string };
  setActionErrorMessage: (message: string) => void;
};

const ActiveRepoCard = styled(Card)(({ theme }) => ({
  border: 0,
  borderRadius: theme.spacing(1),
  padding: `${theme.spacing(2)} ${theme.spacing(2)} ${theme.spacing(2)} ${theme.spacing(3)}`,
  cursor: 'pointer',
  [theme.breakpoints.down('md')]: {
    padding: `${theme.spacing(1)} ${theme.spacing(1)} ${theme.spacing(1)} ${theme.spacing(2)}`,
  },
}));

const InactiveRepoCard = styled(ActiveRepoCard)(({ theme }) => ({
  backgroundColor: theme.palette.grey[50],
  cursor: 'unset',
}));

const InactiveRepo = styled(Card)(({ theme }) => ({
  boxShadow: 'none',
  borderRadius: theme.spacing(1),
  backgroundColor: theme.palette.grey[200],
  padding: `26px ${theme.spacing(2)}`,
}));

const PlaceholderBox = styled('div')(() => ({
  height: 100,
}));

const CloseDialogButton = styled(IconButton)(() => ({
  position: 'relative',
  top: -32,
  right: -32,
}));

const DeactivateCard = styled(Card)(({ theme }) => ({
  width: '100%',
  background: 'rgba(254, 236, 235, 1)',
  padding: `${theme.spacing(2)} ${theme.spacing(3)}`,
  boxShadow: 'unset',
  borderRadius: theme.spacing(1),
}));

const ActivateCard = styled(Card)(({ theme }) => ({
  width: '100%',
  background: 'rgba(0, 169, 183, 0.08)',
  padding: `${theme.spacing(2)} ${theme.spacing(3)}`,
  boxShadow: 'unset',
  borderRadius: theme.spacing(1),
}));

const StyledDialog = styled(Dialog)(({ theme }) => ({
  '& .MuiDialog-paper': {
    padding: theme.spacing(5),
    minWidth: 540,
    [theme.breakpoints.down('md')]: {
      minWidth: 'unset',
    },
  },
  '& .MuiBackdrop-root': {
    backgroundColor: theme.palette.grey[100],
  },
}));

const ActivateRepoDialog = ({ open, close, repo, setActionErrorMessage }: RepoDialogProps) => {
  const queryClient = useQueryClient();
  const { orgSlug, slug, name } = repo;

  const [{ isLoading, mutate }] = useMutationPost(
    [`${QueryNames.ACTIVATE_REPO}/${orgSlug}/${slug}`],
    backendPaths.users_api.REPO(orgSlug, slug),
    null,
    {
      onError: (error: any) => {
        if (error?.error?.detail) {
          setActionErrorMessage(error.error.detail);
        } else {
          setActionErrorMessage('Repo activation failed');
        }
      },
      onSuccess: ({ repo: newRepository }: { repo: Repo }) => {
        queryClient.invalidateQueries([QueryNames.ALL_USER_REPOS]);
        queryClient.setQueryData([`${QueryNames.ORG}/${orgSlug}`], (organization: Organization) => ({
          ...organization,
          repos: organization.repos.map(repository => {
            if (repository.id === newRepository.id) {
              return newRepository;
            } else {
              return repository;
            }
          }),
        }));
        close();
      },
    },
    true
  );

  return (
    <StyledDialog onClose={close} open={open}>
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Grid container justifyContent="space-between">
            <Grid item>
              <Typography variant="h3">You are about to activate this repo</Typography>
            </Grid>
            <Grid>
              <CloseDialogButton aria-label="close activate dialog" onClick={close} disabled={isLoading} size="large">
                <CloseIcon color="primary" />
              </CloseDialogButton>
            </Grid>
          </Grid>
        </Grid>
        <Grid item xs={12}>
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <ActivateCard>
                <Grid container spacing={1}>
                  <Grid item xs={12}>
                    <Typography variant="subtitle1">{name}</Typography>
                  </Grid>
                  <Grid item xs={12}>
                    <Typography variant="body1">{slug}</Typography>
                  </Grid>
                </Grid>
              </ActivateCard>
            </Grid>
            <Grid item xs={12}>
              <Typography variant="body3">Toolchain will register webhooks with the repo.</Typography>
            </Grid>
          </Grid>
        </Grid>
        <Grid item xs={12}>
          <Grid container spacing={2} justifyContent="flex-end" alignItems="center">
            <Grid item>
              <Button onClick={close} disabled={isLoading}>
                <Typography variant="button3" color="primary">
                  CANCEL
                </Typography>
              </Button>
            </Grid>
            <Grid item>
              <Button
                aria-label="activate repo"
                variant="contained"
                onClick={() => mutate({})}
                color="primary"
                disabled={isLoading}
              >
                <Typography variant="button3">ACTIVATE</Typography>
              </Button>
            </Grid>
          </Grid>
        </Grid>
      </Grid>
    </StyledDialog>
  );
};
const DeactivateRepoDialog = ({ open, close, repo, setActionErrorMessage }: RepoDialogProps) => {
  const queryClient = useQueryClient();
  const { orgSlug, slug, name } = repo;

  const [{ isLoading, mutate }] = useMutationDelete(
    [`${QueryNames.DEACTIVATE_REPO}/${orgSlug}/${slug}`],
    backendPaths.users_api.REPO(orgSlug, slug),
    {
      onError: (error: any) => {
        if (error?.error?.detail) {
          setActionErrorMessage(error.error.detail);
        } else {
          setActionErrorMessage('Repo deactivation failed');
        }
      },
      onSuccess: ({ repo: newRepository }: { repo: Repo }) => {
        queryClient.invalidateQueries([QueryNames.ALL_USER_REPOS]);
        queryClient.setQueryData([`${QueryNames.ORG}/${orgSlug}`], (organization: Organization) => ({
          ...organization,
          repos: organization.repos.map(repository => {
            if (repository.id === newRepository.id) {
              return newRepository;
            } else {
              return repository;
            }
          }),
        }));
        close();
      },
    },
    true
  );

  return (
    <StyledDialog onClose={close} open={open}>
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Grid container justifyContent="space-between">
            <Grid item>
              <Typography variant="h3">You are about to deactivate this repo</Typography>
            </Grid>
            <Grid>
              <CloseDialogButton aria-label="close deactivate dialog" onClick={close} disabled={isLoading} size="large">
                <CloseIcon color="primary" />
              </CloseDialogButton>
            </Grid>
          </Grid>
        </Grid>
        <Grid item xs={12}>
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <DeactivateCard>
                <Grid container spacing={1}>
                  <Grid item xs={12}>
                    <Typography variant="subtitle1">{name}</Typography>
                  </Grid>
                  <Grid item xs={12}>
                    <Typography variant="body1">{slug}</Typography>
                  </Grid>
                </Grid>
              </DeactivateCard>
            </Grid>
            <Grid item xs={12}>
              <Typography variant="body3">Toolchain will de-register webhooks with the repo.</Typography>
            </Grid>
          </Grid>
        </Grid>
        <Grid item xs={12}>
          <Grid container spacing={2} justifyContent="flex-end" alignItems="center">
            <Grid item>
              <Button onClick={close} disabled={isLoading}>
                <Typography variant="button3" color="primary">
                  KEEP IT
                </Typography>
              </Button>
            </Grid>
            <Grid item>
              <Button
                aria-label="deactivate repo"
                variant="contained"
                onClick={() => mutate({})}
                color="error"
                disabled={isLoading}
              >
                <Typography variant="button3">DEACTIVATE</Typography>
              </Button>
            </Grid>
          </Grid>
        </Grid>
      </Grid>
    </StyledDialog>
  );
};

const RepoCard = ({ name, slug, isActive, orgSlug, isManagingRepos, isAdmin }: RepoCardProps) => {
  const navigate = useNavigate();
  const [isOpenActivate, setIsOpenActivate] = useState(false);
  const [isOpenDeactivate, setIsOpenDeactivate] = useState(false);
  const [isBeingHovered, setIsBeingHovered] = useState(false);
  const [actionErrorMessage, setActionErrorMessage] = useState<string | null>(null);

  const openActivate = (event: React.MouseEvent<HTMLElement>) => {
    event.stopPropagation();
    setIsOpenActivate(true);
  };
  const openDeactivate = (event: React.MouseEvent<HTMLElement>) => {
    event.stopPropagation();
    setIsOpenDeactivate(true);
  };
  const closeActivate = () => setIsOpenActivate(false);
  const closeDeactivate = () => setIsOpenDeactivate(false);
  const goToBuilds = () => {
    navigate({ pathname: paths.builds(orgSlug, slug), search: '?user=me' });
  };

  const showActionError = actionErrorMessage && !!actionErrorMessage.length;
  const CardComponent = isActive ? ActiveRepoCard : InactiveRepoCard;
  const repo = { name, slug, orgSlug };

  const CardInfo = () => {
    const buttonText = isActive ? 'DEACTIVATE' : 'ACTIVATE';
    const buttonColor = isActive ? 'error' : 'primary';
    const buttonOnClick = isActive ? openDeactivate : openActivate;

    if (isAdmin && isManagingRepos) {
      return (
        <Grid item xs={6}>
          <Grid container justifyContent="flex-end">
            <Button variant="contained" color={buttonColor} onClick={buttonOnClick} sx={{ margin: '31.75px 0' }}>
              {buttonText}
            </Button>
          </Grid>
        </Grid>
      );
    }

    if (!isActive) {
      return (
        <Grid item xs={6}>
          <Grid container justifyContent="flex-end">
            {isAdmin && isBeingHovered ? (
              <Button
                variant="contained"
                color="primary"
                onClick={event => {
                  setIsBeingHovered(false);
                  openActivate(event);
                }}
                sx={{ margin: '31.75px 0' }}
              >
                ACTIVATE
              </Button>
            ) : (
              <InactiveRepo>
                <Typography variant="body1" align="center" color="text.disabled">
                  Inactive <br />
                  repo
                </Typography>
              </InactiveRepo>
            )}
          </Grid>
        </Grid>
      );
    } else {
      return <PlaceholderBox />;
    }
  };

  return (
    <>
      <Grid item xs={12} md={6}>
        <CardComponent
          variant="outlined"
          onClick={isActive ? goToBuilds : null}
          onMouseEnter={() => setIsBeingHovered(true)}
          onMouseLeave={() => setIsBeingHovered(false)}
        >
          <Grid container justifyContent="space-between" alignItems="center">
            <Grid item xs={6}>
              <Grid container spacing={1}>
                <Grid item xs={12}>
                  <Typography variant="h3" color="text.primary">
                    {slug}
                  </Typography>
                </Grid>
                <Grid item xs={12}>
                  <Typography variant="body1" color="text.primary">
                    {name}
                  </Typography>
                </Grid>
              </Grid>
            </Grid>
            <CardInfo />
          </Grid>
        </CardComponent>
      </Grid>
      <ActivateRepoDialog
        open={isOpenActivate}
        close={closeActivate}
        repo={repo}
        setActionErrorMessage={setActionErrorMessage}
      />
      <DeactivateRepoDialog
        open={isOpenDeactivate}
        close={closeDeactivate}
        repo={repo}
        setActionErrorMessage={setActionErrorMessage}
      />
      <Snackbar
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        autoHideDuration={5000}
        open={showActionError}
        onClose={() => setActionErrorMessage(null)}
      >
        <Alert icon={false} severity="error" variant="filled" onClose={() => setActionErrorMessage(null)}>
          {actionErrorMessage}
        </Alert>
      </Snackbar>
    </>
  );
};

export default RepoCard;
