/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';
import { styled } from '@mui/material/styles';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import AddCircleOutline from '@mui/icons-material/AddCircleOutline';
import IconButton from '@mui/material/IconButton';
import Snackbar from '@mui/material/Snackbar';
import Button from '@mui/material/Button';
import { useQueryClient } from '@tanstack/react-query';
import Dialog from '@mui/material/Dialog';
import CloseIcon from '@mui/icons-material/Close';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import TextField from '@mui/material/TextField';
import { StringParam, useQueryParams } from 'use-query-params';
import FileCopyIcon from '@mui/icons-material/FileCopy';

import { WorkerToken, WorkerTokensResponse, WorkerTokenState } from 'common/interfaces/worker-tokens';
import { TableData, TableSort, TableColumns } from 'common/interfaces/table';
import QueryNames from 'common/enums/QueryNames';
import { useMutationDelete, useMutationPost, useQueryGet } from 'utils/hooks/query';
import backendPaths from 'utils/backend-paths';
import BreadCrumbs from 'components/breadrumbs/breadcrumbs';
import Table, { TableQueryChange } from 'components/tables/table';
import { dateToDateTimeWithSeparator, isAfter, isBefore } from 'utils/datetime-formats';
import { useRequestErrorContext } from 'store/request-error-store';

type RevealTokenProps = { token: string; setActionSuccessMessage: (text: string) => void };
type DialogProps = {
  open: boolean;
  closeDialog: () => void;
  token?: WorkerToken;
  setErrorMessage: (text: string) => void;
  setSuccessMessage: (text: string) => void;
};

const StyledChip = styled(Chip, { shouldForwardProp: propName => propName !== 'isWorkerTokenActive' })<{
  isWorkerTokenActive: boolean;
}>(({ theme, isWorkerTokenActive }) => ({
  backgroundColor: isWorkerTokenActive ? theme.palette.success.main : theme.palette.grey[300],
}));

const StyledVisiblityIcon = styled(VisibilityIcon)(({ theme }) => ({
  color: theme.palette.text.secondary,
  fontSize: 24,
}));
const StyledVisibilityOffIcon = StyledVisiblityIcon.withComponent(VisibilityOffIcon);

const WrapAnywhereTypography = styled(Typography)(() => ({
  overflowWrap: 'anywhere',
}));

const BluredTypography = styled(WrapAnywhereTypography)(() => ({
  filter: `blur(4px)`,
  userSelect: 'none',
}));

const StyledDialog = styled(Dialog)(({ theme }) => ({
  [`& .MuiPaper-root`]: {
    padding: theme.spacing(5),
    minWidth: 540,
    [theme.breakpoints.down('md')]: {
      minWidth: 'unset',
    },
  },
  [`& .MuiBackdrop-root`]: {
    backgroundColor: theme.palette.grey[100],
  },
}));

const CloseDialogButton = styled(IconButton)(({ theme }) => ({
  position: 'absolute',
  top: theme.spacing(1),
  right: theme.spacing(1),
}));

const SuccessSnackbar = styled(Snackbar)(() => ({
  [` .MuiPaper-root`]: {
    backgroundColor: 'rgba(28, 43, 57, 1)',
  },
}));

const TypographyWithPadding = styled(Typography)(() => ({
  padding: `11.5px 0px`,
}));

const StyledInfoBox = styled(Box)(({ theme }) => ({
  backgroundColor: 'rgba(237, 247, 237, 1)',
  borderRadius: theme.spacing(1),
  padding: `${theme.spacing(1)} ${theme.spacing(2)}`,
}));

const DeactivateDialog = ({ open, closeDialog, token, setSuccessMessage, setErrorMessage }: DialogProps) => {
  const queryClient = useQueryClient();
  const { orgSlug } = useParams();

  const [{ isLoading, mutate }] = useMutationDelete(
    [`${QueryNames.WORKER_TOKEN}_${token?.id}`],
    backendPaths.users_api.WORKER_TOKEN(orgSlug, token?.id),
    {
      onError: (error: any) => {
        if (error.errors.token) {
          setErrorMessage(error.errors.token.join('. '));
        } else {
          setErrorMessage('Token deactivation failed');
        }
        closeDialog();
      },
      onSuccess: () => {
        closeDialog();
        setSuccessMessage('Token deactivated');
        queryClient.invalidateQueries([QueryNames.WORKER_TOKENS]);
      },
    }
  );

  const close = () => !isLoading && closeDialog();

  return (
    <StyledDialog onClose={close} aria-labelledby="table-dialog-title" open={open}>
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Grid container justifyContent="space-between">
            <Grid item>
              <Typography variant="h3">Deactivating token</Typography>
            </Grid>
            <CloseDialogButton aria-label="close deactivate" onClick={closeDialog} disabled={isLoading} size="large">
              <CloseIcon color="primary" />
            </CloseDialogButton>
          </Grid>
        </Grid>
        <Grid item xs={12}>
          <StyledInfoBox>
            <Grid container spacing={1}>
              <Grid item xs={12}>
                <Typography variant="body3" color="success.dark">
                  Description: {token?.description}
                </Typography>
              </Grid>
              <Grid item xs={12}>
                <Typography variant="body3" color="success.dark">
                  Created at: {dateToDateTimeWithSeparator(token?.created_at)}
                </Typography>
              </Grid>
            </Grid>
          </StyledInfoBox>
        </Grid>
        <Grid item xs={12}>
          <Typography variant="body3" component="div">
            You will not be able to reactivate the token after this. Do you want to continue?
          </Typography>
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
                aria-label="deactivate token"
                variant="contained"
                color="error"
                onClick={() => mutate({})}
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

const GenerateDialog = ({ open, closeDialog, setSuccessMessage, setErrorMessage }: DialogProps) => {
  const queryClient = useQueryClient();
  const { orgSlug } = useParams();
  const [description, setDescription] = useState('');
  const [descriptionError, setDescriptionError] = useState<string | false>(false);

  const payload = description
    ? JSON.stringify({
        description: description?.trim(),
      })
    : null;

  const [{ isLoading, mutate }] = useMutationPost(
    [QueryNames.WORKER_TOKENS],
    backendPaths.users_api.WORKER_TOKENS(orgSlug),
    payload,
    {
      onError: (error: any) => {
        if (error.errors.description) {
          setDescriptionError(error.errors.description.map((err: { message: string }) => err.message).join('. '));
        } else {
          setDescriptionError(false);
          setErrorMessage('Token generation failed');
          closeDialog();
        }
      },
      onSuccess: () => {
        closeDialog();
        setSuccessMessage('Token generated');
        queryClient.invalidateQueries([QueryNames.WORKER_TOKENS]);
      },
    }
  );

  const close = () => {
    if (!isLoading) {
      closeDialog();
      setDescription('');
      setDescriptionError(false);
    }
  };

  const generateToken = () => mutate({});
  const handleDescriptionChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { value } = event.target;
    const trimedValue = value.trim();
    const maxCharLength = 256;

    if (trimedValue && trimedValue.length > maxCharLength) {
      setDescriptionError(`Description can't be more than ${maxCharLength} characters.`);
    } else {
      setDescriptionError(false);
    }

    setDescription(value);
  };

  const isGenerateDisabled = isLoading || !!descriptionError;

  return (
    <StyledDialog onClose={close} aria-labelledby="table-dialog-title" open={open}>
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Grid container justifyContent="space-between">
            <Grid item>
              <Typography variant="h3">Add a description for the new token</Typography>
            </Grid>
            <CloseDialogButton aria-label="close create" onClick={close} disabled={isLoading} size="large">
              <CloseIcon color="primary" />
            </CloseDialogButton>
          </Grid>
        </Grid>
        <Grid item xs={12}>
          <Typography variant="body1">This is optional. If left empty, a default value will be assigned.</Typography>
        </Grid>
        <Grid item xs={12}>
          <TextField
            id="description-input"
            aria-describedby="description-text-worker"
            error={!!descriptionError}
            helperText={descriptionError}
            value={description}
            onChange={handleDescriptionChange}
            inputProps={{ 'aria-label': 'description' }}
            fullWidth={true}
          />
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
                aria-label="generate token"
                variant="contained"
                color="primary"
                onClick={generateToken}
                disabled={isGenerateDisabled}
              >
                <Typography variant="button3" color="white">
                  GENERATE
                </Typography>
              </Button>
            </Grid>
          </Grid>
        </Grid>
      </Grid>
    </StyledDialog>
  );
};

const RevealToken = ({ token, setActionSuccessMessage }: RevealTokenProps) => {
  const [isVisible, setIsVisible] = useState(false);
  const icon = isVisible ? <StyledVisibilityOffIcon /> : <StyledVisiblityIcon />;
  const text = isVisible ? (
    <WrapAnywhereTypography variant="body2">{token}</WrapAnywhereTypography>
  ) : (
    <BluredTypography variant="body2">{token}</BluredTypography>
  );
  const copyToClipboard = (tokenValue: string) => {
    navigator.clipboard.writeText(tokenValue);
    setActionSuccessMessage('Token value copied');
  };

  return (
    <Grid
      container
      spacing={2}
      alignItems="center"
      onMouseLeave={() => {
        if (isVisible) {
          setIsVisible(!isVisible);
        }
      }}
      wrap="nowrap"
      justifyContent="space-between"
    >
      <Grid item>{text}</Grid>
      <Grid item>
        <Grid container>
          <Grid item xs={6}>
            <IconButton onClick={() => setIsVisible(!isVisible)}>{icon}</IconButton>
          </Grid>
          <Grid item xs={6}>
            <IconButton onClick={() => copyToClipboard(token)}>
              <FileCopyIcon />
            </IconButton>
          </Grid>
        </Grid>
      </Grid>
    </Grid>
  );
};

const sortTokens = (data: WorkerTokensResponse, sort: TableSort) => {
  const { order, orderBy } = sort;
  const isAscending = order === 'asc';
  const sortedTokens = [...data.tokens];
  const key = orderBy as keyof WorkerToken;

  const dateSortFunction = isAscending ? isAfter : isBefore;

  switch (orderBy) {
    case 'created_at':
      sortedTokens.sort((a, b) => (dateSortFunction(a[key], b[key]) ? 1 : -1));
      break;
    default:
      sortedTokens.sort((a, b) => {
        const isValidKey = orderBy in a || orderBy in b;
        if (isValidKey) {
          return isAscending ? b[key].localeCompare(a[key]) : a[key].localeCompare(b[key]);
        }
      });
      break;
  }

  return { tokens: sortedTokens };
};

const WorkerTokens = () => {
  const { orgSlug } = useParams();
  const [query, updateQuery] = useQueryParams({ sort: StringParam });
  const { setErrorMessage } = useRequestErrorContext();
  const [showError, toggleShowError] = useState(true);
  const [currentToken, setCurrentToken] = useState<WorkerToken>(null);
  const [isOpenDeactivate, setIsOpenDeactivate] = useState(false);
  const [isOpenGenerate, setIsOpenGenerate] = useState(false);
  const [actionErrorMessage, setActionErrorMessage] = useState<string | null>(null);
  const [actionSuccessMessage, setActionSuccessMessage] = useState<string | null>(null);

  const closeDeactivate = () => {
    setIsOpenDeactivate(false);
    setCurrentToken(null);
  };

  const closeGenerate = () => {
    setIsOpenGenerate(false);
    setCurrentToken(null);
  };

  const handleQueryChange: TableQueryChange = (type, values?) => {
    updateQuery(
      {
        ...values,
      },
      'pushIn'
    );
  };

  const [{ data, isFetching, errorMessage }] = useQueryGet<WorkerTokensResponse>(
    [QueryNames.WORKER_TOKENS],
    backendPaths.users_api.WORKER_TOKENS(orgSlug)
  );

  if (showError && errorMessage) {
    return (
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
    );
  }

  const hasSorting = query?.sort;
  const isDescending = hasSorting && query.sort.charAt(0) === '-';
  const order: 'asc' | 'desc' = hasSorting ? (isDescending ? 'desc' : 'asc') : 'desc';
  const orderBy = hasSorting ? (isDescending ? query.sort.slice(1) : query.sort) : 'state';
  const sort: TableSort = { order, orderBy };

  const sortedData = data && sortTokens(data, sort);

  const tableData: TableData<WorkerToken> = sortedData?.tokens.map(token => ({
    id: token.id,
    token: token,
    description: token,
    state: token,
    created_at: token,
    deactivate: token,
  }));

  const tableColumns: TableColumns<WorkerToken> = {
    token: {
      sortable: false,
      sortName: null,
      label: 'TOKEN',
      width: 600,
      renderValue: ({ token }: WorkerToken) =>
        token ? (
          <RevealToken token={token} setActionSuccessMessage={setActionSuccessMessage} />
        ) : (
          <TypographyWithPadding variant="body2">Not available</TypographyWithPadding>
        ),
    },
    description: {
      sortable: true,
      sortName: 'description',
      label: 'DESCRIPTION',
      renderValue: ({ description }: WorkerToken) => (
        <WrapAnywhereTypography variant="body2">{description}</WrapAnywhereTypography>
      ),
    },
    state: {
      sortable: true,
      sortName: 'state',
      label: 'STATE',
      width: 120,
      renderValue: ({ state }: WorkerToken) => {
        const isWorkerTokenActive = state === WorkerTokenState.ACTIVE;
        const textColor = isWorkerTokenActive ? 'common.white' : 'text.primary';

        return (
          <StyledChip
            isWorkerTokenActive={isWorkerTokenActive}
            label={
              <Typography variant="caption" color={textColor} textTransform="capitalize">
                {state}
              </Typography>
            }
          />
        );
      },
    },
    created_at: {
      sortable: true,
      sortName: 'created_at',
      label: 'CREATED AT',
      width: 200,
      renderValue: ({ created_at }: WorkerToken) => (
        <Typography variant="body2">{dateToDateTimeWithSeparator(created_at)}</Typography>
      ),
    },
    deactivate: {
      sortable: false,
      sortName: null,
      label: '',
      width: 116,
      renderValue: (token: WorkerToken) => {
        const isWorkerTokenActive = token.state === WorkerTokenState.ACTIVE;

        return isWorkerTokenActive ? (
          <Button
            onClick={() => {
              setCurrentToken(token);
              setIsOpenDeactivate(true);
            }}
            color="error"
            variant="text"
          >
            <Typography variant="button3" color="error">
              DEACTIVATE
            </Typography>
          </Button>
        ) : null;
      },
    },
  };

  const showActionSuccess = actionSuccessMessage && !!actionSuccessMessage.length;
  const showActionError = actionErrorMessage && !!actionErrorMessage.length;

  return (
    <>
      <Grid container spacing={5}>
        <Grid item xs={12}>
          <Grid container spacing={1}>
            <Grid item xs={12}>
              <BreadCrumbs org={orgSlug} />
            </Grid>
            <Grid item xs={12}>
              <Grid container justifyContent="space-between" alignItems="center">
                <Grid item>
                  <Typography variant="h2">Worker tokens</Typography>
                </Grid>
                <Grid item>
                  <Button
                    variant="outlined"
                    color="primary"
                    startIcon={<AddCircleOutline />}
                    onClick={() => setIsOpenGenerate(true)}
                  >
                    <Typography variant="button1">GENERATE NEW TOKEN</Typography>
                  </Button>
                </Grid>
              </Grid>
            </Grid>
          </Grid>
        </Grid>
        <Grid item xs={12}>
          <Table
            name="worker tokens"
            sort={sort}
            columns={tableColumns}
            data={tableData}
            isLoading={isFetching}
            onQueryChange={handleQueryChange}
          />
        </Grid>
      </Grid>
      <DeactivateDialog
        open={isOpenDeactivate}
        token={currentToken}
        closeDialog={closeDeactivate}
        setSuccessMessage={setActionSuccessMessage}
        setErrorMessage={setActionErrorMessage}
      />
      <GenerateDialog
        open={isOpenGenerate}
        closeDialog={closeGenerate}
        setSuccessMessage={setActionSuccessMessage}
        setErrorMessage={setActionErrorMessage}
      />
      <SuccessSnackbar
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        autoHideDuration={5000}
        open={showActionSuccess}
        onClose={() => setActionSuccessMessage(null)}
        message={actionSuccessMessage}
        action={
          <IconButton size="small" aria-label="close" color="inherit" onClick={() => setActionSuccessMessage(null)}>
            <CloseIcon />
          </IconButton>
        }
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

export default WorkerTokens;
