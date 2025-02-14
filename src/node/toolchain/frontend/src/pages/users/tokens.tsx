/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useQueryParams, StringParam } from 'use-query-params';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Tooltip from '@mui/material/Tooltip';
import Snackbar from '@mui/material/Snackbar';
import Button from '@mui/material/Button';
import CloseIcon from '@mui/icons-material/Close';
import Edit from '@mui/icons-material/Edit';
import Dialog from '@mui/material/Dialog';
import IconButton from '@mui/material/IconButton';
import Alert from '@mui/material/Alert';
import FormControl from '@mui/material/FormControl';
import TextField from '@mui/material/TextField';

import { useMutationDelete, useMutationPatch, useQueryGet } from 'utils/hooks/query';
import QueryNames from 'common/enums/QueryNames';
import backendPaths from 'utils/backend-paths';
import { GetTokensResponse, Token, TokenState } from 'common/interfaces/token';
import { TableData, TableColumns, TableSort } from 'common/interfaces/table';
import Table, { TableQueryChange } from 'components/tables/table';
import TextChip from 'components/chips/text-chip/text-chip';
import { isAfter, isBefore, stringToDate, isOlderThan24Hours, utcTimeAgo } from 'utils/datetime-formats';
import paths from 'utils/paths';
import { useQueryClient } from '@tanstack/react-query';
import { useRequestErrorContext } from 'store/request-error-store';
import { styled, Theme } from '@mui/material/styles';

const createNewTokenInfoLink = 'https://docs.toolchain.com/docs#local-development-for-each-user';

enum TokenBoxColor {
  Active = 'rgba(237, 247, 237, 1)',
  Expired = 'rgba(0, 0, 0, 0.12)',
  Revoked = 'rgba(254, 236, 235, 1)',
}

type DialogProps = {
  open: boolean;
  closeDialog: () => void;
  token: Token;
  setErrorMessage: (text: string) => void;
  setSuccessMessage: (text: string) => void;
};
type StyledBoxType = {
  backgroundColor: TokenBoxColor;
};
type StyledTextChipGridItemProps = { state: TokenState };

const TokenTooltipLink = styled('a')(({ theme }) => ({
  color: theme.palette.primary.main,
  cursor: 'pointer',
}));

const RepoInfoFirstRow = styled(Typography)(({ theme }) => ({
  [theme.breakpoints.down('md')]: {
    marginRight: theme.spacing(0.5),
  },
}));

const CloseDialogButton = styled(IconButton)(() => ({
  position: 'relative',
  top: -32,
  right: -32,
}));

const RevokeButton = styled(Button)(({ theme }) => ({
  backgroundColor: theme.palette.error.main,
  color: theme.palette.common.white,
  [`&:hover`]: {
    backgroundColor: theme.palette.error.main,
  },
}));

const RevokeButtonBorder = styled(Box)(({ theme }) => ({
  [theme.breakpoints.down('md')]: {
    margin: `0 ${theme.spacing(1)}`,
    borderTop: '1px solid #e0e0e0',
    width: '100%',
  },
}));

const RevokeButtonContainer = styled(Box)(({ theme }) => ({
  [theme.breakpoints.down('md')]: {
    padding: `2px 0 2px ${theme.spacing(1)}`,
  },
}));

const DescriptionContainer = styled(Grid)(({ theme }) => ({
  [theme.breakpoints.down('md')]: {
    flexWrap: 'wrap',
    margin: `${theme.spacing(2)} ${theme.spacing(2)} ${theme.spacing(0.5)}`,
    width: `calc(100% - ${theme.spacing(4)})`,
  },
}));

const StyledIconButton = styled(IconButton)(({ theme }) => ({
  padding: theme.spacing(1),
  [theme.breakpoints.down('md')]: {
    marginLeft: theme.spacing(3),
  },
  [theme.breakpoints.down('sm')]: {
    marginLeft: 0,
  },
}));

const StyledLink = styled(Link)(({ theme }) => ({
  color: theme.palette.primary.main,
}));

const PermissionContainer = styled(Grid)(({ theme }) => ({
  [theme.breakpoints.down('md')]: {
    margin: `0 ${theme.spacing(1)}`,
    padding: `0 ${theme.spacing(0.5)}`,
    borderBottom: '1px solid #e0e0e0',
    width: `calc(100% - ${theme.spacing(2)})`,
    display: 'flex',
    justifyContent: 'space-between',
  },
  [theme.breakpoints.down('sm')]: {
    display: 'flex',
    flexDirection: 'column',
  },
}));

const PermSecondRow = styled(Grid)(({ theme }) => ({
  display: 'block',
  [`&:not(:empty)`]: {
    marginBottom: theme.spacing(0.5),
  },
}));

const LastSeenBox = styled(Box)(({ theme }) => ({
  minHeight: 52,
  borderLeft: `1px solid ${theme.palette.grey['300']}`,
  paddingLeft: theme.spacing(2),
  paddingTop: theme.spacing(2),
  paddingBottom: theme.spacing(2),
  marginLeft: `-${theme.spacing(2)}`,
  [theme.breakpoints.down('md')]: {
    display: 'flex',
    flexDirection: 'column',
    padding: 0,
    minHeight: 'unset',
    margin: `${theme.spacing(1)} 0 ${theme.spacing(1)} ${theme.spacing(2)}`,
    borderLeft: 0,
  },
}));

const LastTimeMobileLabel = styled(Typography)(({ theme }) => ({
  display: 'none',
  [theme.breakpoints.down('md')]: {
    display: 'block',
  },
}));

const LastTimeMobileBox = styled(Box)(({ theme }) => ({
  [theme.breakpoints.down('md')]: {
    display: 'flex',
    flexDirection: 'column',
    margin: `${theme.spacing(1)} 0 ${theme.spacing(1)} ${theme.spacing(2)}`,
  },
}));

const RepoInfoContainer = styled(Grid)(({ theme }) => ({
  [theme.breakpoints.down('md')]: {
    margin: `${theme.spacing(1)} ${theme.spacing(1)} 0`,
    padding: `0 ${theme.spacing(1)} ${theme.spacing(1)}`,
    borderBottom: '1px solid #e0e0e0',
    width: `calc(100% - ${theme.spacing(2)})`,
  },
}));

const RepoInfoText = styled(Typography)(({ theme }) => ({
  [theme.breakpoints.down('md')]: {
    margin: `${theme.spacing(1)} ${theme.spacing(1)} 0`,
    padding: `0 ${theme.spacing(1)} ${theme.spacing(1)}`,
    borderBottom: '1px solid #e0e0e0',
    width: `calc(100% - ${theme.spacing(2)})`,
  },
}));

const TokenInfoBox = styled(Box)(({ theme }) => ({
  padding: `${theme.spacing(1)} 0px`,
  background: 'rgba(237, 247, 237, 1)',
  borderRadius: theme.spacing(1),
}));

const TokenInfoText = styled(Typography)(({ theme }) => ({
  textAlign: 'center',
  color: theme.palette.success.dark,
}));

const SuccessSnackbar = styled(Snackbar)(() => ({
  [` .MuiPaper-root`]: {
    backgroundColor: 'rgba(28, 43, 57, 1)',
  },
}));

const StyledFormControl = styled(FormControl)(() => ({
  [`&.MuiFormControl-root`]: {
    width: '100%',
  },
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

const StyledTextChipGridItem = styled(Grid, {
  shouldForwardProp: prop => prop !== 'state',
})<StyledTextChipGridItemProps>(({ theme, state }) => {
  const CHIP_COLOR = {
    [TokenState.ACTIVE]: theme.palette.success.main,
    [TokenState.EXPIRED]: theme.palette.action.disabled,
    [TokenState.REVOKED]: theme.palette.error.main,
  };

  return {
    [`& .MuiChip-root`]: {
      color: theme.palette.common.white,
      background: CHIP_COLOR[state],
    },
  };
});

const StyledBox = styled(Box)<StyledBoxType>(({ theme, backgroundColor }) => ({
  padding: `2px ${theme.spacing(2)} 2px 2px`,
  border: 0,
  borderRadius: theme.spacing(3),
  [theme.breakpoints.down('md')]: {
    padding: 0,
  },
  background: backgroundColor,
}));

const rowStyles = (theme: Theme) => ({
  [`& td`]: {
    position: 'relative',
    [theme.breakpoints.down('md')]: {
      display: 'block',
      width: 'calc(100% - 16px)',
      padding: 0,
    },
    [`&:first-of-type`]: {
      width: 160,
      [theme.breakpoints.down('md')]: {
        width: '100%',
      },
    },
    [`&:nth-of-type(2)`]: {
      width: 300,
      [theme.breakpoints.down('md')]: {
        width: '100%',
      },
    },
    [`&:nth-of-type(3)`]: {
      width: 290,
      [theme.breakpoints.down('md')]: {
        width: '100%',
      },
    },
    [`&:nth-of-type(4)`]: {
      width: 118,
      [theme.breakpoints.down('md')]: {
        width: 'unset',
        display: 'inline-block',
      },
    },
    [`&:nth-of-type(5)`]: {
      width: 120,
      [theme.breakpoints.down('md')]: {
        width: 'unset',
        display: 'inline-block',
      },
    },
    [`&:nth-of-type(6)`]: {
      width: 120,
      [theme.breakpoints.down('md')]: {
        width: 'unset',
        display: 'inline-block',
      },
    },
    [`&:nth-of-type(7)`]: {
      width: 92,
      [`& button`]: {
        opacity: 0,
        [theme.breakpoints.down('md')]: {
          opacity: 1,
        },
      },
      [theme.breakpoints.down('md')]: {
        width: `calc(100% - ${theme.spacing(2)})`,
      },
    },
  },
});

const bodyRowStyles = (theme: Theme) => ({
  [`&:hover`]: {
    [`& td`]: {
      borderTop: '1px solid rgba(0, 169, 183, 0.5)',
      borderBottom: '1px solid rgba(0, 169, 183, 0.5)',
      [`&:first-of-type`]: {
        borderLeft: '1px solid rgba(0, 169, 183, 0.5)',
        borderTopLeftRadius: 8,
        borderBottomLeftRadius: 8,
        [theme.breakpoints.down('md')]: {
          borderLeft: '1px solid transparent',
        },
      },
      [`&:last-of-type`]: {
        borderRight: '1px solid rgba(0, 169, 183, 0.5)',
        borderTopRightRadius: 8,
        borderBottomRightRadius: 8,
        [`& button`]: {
          opacity: 1,
        },
        [theme.breakpoints.down('md')]: {
          borderRight: '1px solid transparent',
        },
      },
      [theme.breakpoints.down('md')]: {
        borderTop: '1px solid transparent',
        borderBottom: '1px solid transparent',
      },
    },
  },
  [`& td`]: {
    height: 84,
    maxHeight: 84,
    borderTop: '1px solid transparent',
    borderBottom: '1px solid transparent',
    [theme.breakpoints.down('md')]: {
      height: 'unset',
      maxHeight: 'unset',
    },
  },
});

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const CustomTooltip = ({ className, ...props }: any) => <Tooltip {...props} classes={{ tooltip: className }} />;

const TokenTooltipInfo = () => {
  return (
    <Typography variant="body1">
      This is the token ID. The token value is only visible when you first create it. Click{' '}
      <TokenTooltipLink href={createNewTokenInfoLink} target="_blank" rel="noopener noreferrer">
        here
      </TokenTooltipLink>{' '}
      for information on how to create a new token.
    </Typography>
  );
};

const Permissions = ({ permissions }: any) => {
  const permissionsViewLimit = 3;

  const renderPermissions = (permissionsArray: string[]) =>
    permissionsArray.map(goal => <TextChip key={goal} text={goal} />);

  if (permissions?.length <= permissionsViewLimit) {
    return <>{renderPermissions(permissions)}</>;
  }

  if (permissions?.length > permissionsViewLimit) {
    const slicedPermissions = permissions.slice(0, permissionsViewLimit);
    const extraPermissionsNumber = permissions.length - slicedPermissions.length;

    return (
      <Tooltip title={permissions.join(', ')} placement="top-end" arrow>
        <Grid container alignItems="center">
          <Grid item>{renderPermissions(slicedPermissions)}</Grid>
          <Grid item>
            <Typography variant="body2">+{extraPermissionsNumber}</Typography>
          </Grid>
        </Grid>
      </Tooltip>
    );
  }

  return null;
};

const sortTokens = (data: Pick<GetTokensResponse, 'tokens'>, sort: TableSort) => {
  const { order, orderBy } = sort;
  const isAscending = order === 'asc';
  const sortedTokens = [...data.tokens];

  const dateSortFunction = isAscending ? isAfter : isBefore;

  switch (orderBy) {
    case 'state':
      sortedTokens.sort((a, b) => {
        if (isAscending) {
          return a.state.localeCompare(b.state);
        }

        return b.state.localeCompare(a.state);
      });
      break;
    default:
      sortedTokens.sort((a, b) => (dateSortFunction((a as any)[orderBy], (b as any)[orderBy]) ? 1 : -1));
      break;
  }

  return sortedTokens;
};

const ActionDialog = ({ open, onClose, children }: any) => {
  return (
    <StyledDialog onClose={onClose} aria-labelledby="table-dialog-title" open={open}>
      {children}
    </StyledDialog>
  );
};

const RevokeDialog = ({ open, closeDialog, token, setSuccessMessage, setErrorMessage }: DialogProps) => {
  const queryClient = useQueryClient();

  const wasRecentlyUsed = token?.last_seen && isOlderThan24Hours(token?.last_seen);
  const tokenString = token && `${token.description} (${token.id})`;

  const [{ isLoading, mutate }] = useMutationDelete(
    [QueryNames.PATCH_USER],
    backendPaths.users_api.REVOKE_TOKEN(token && token.id),
    {
      onError: (error: any) => {
        if (error.token) {
          setErrorMessage(error.token.join('. '));
        } else {
          setErrorMessage('Token revoke failed');
        }
        closeDialog();
      },
      onSuccess: () => {
        closeDialog();
        setSuccessMessage('Token has been revoked');
        queryClient.invalidateQueries([QueryNames.TOKENS]);
      },
    }
  );

  const close = () => !isLoading && closeDialog();

  return (
    <>
      <ActionDialog onClose={close} open={open}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Grid container justifyContent="space-between">
              <Grid item>
                <Typography variant="h3">Revoking token</Typography>
              </Grid>
              <Grid>
                <CloseDialogButton aria-label="close revoke" onClick={closeDialog} disabled={isLoading} size="large">
                  <CloseIcon color="primary" />
                </CloseDialogButton>
              </Grid>
            </Grid>
          </Grid>
          <Grid item xs={12}>
            <TokenInfoBox>
              <TokenInfoText variant="body3" align="center">
                {tokenString}
              </TokenInfoText>
            </TokenInfoBox>
          </Grid>
          <Grid item xs={12}>
            <Typography variant="body3" component="div">
              {wasRecentlyUsed && (
                <Box fontWeight="fontWeightMedium" display="inline">
                  You have used this token within the past 24 hours.{' '}
                </Box>
              )}
              This action cannot be undone. Do you want to continue?
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
                <RevokeButton
                  aria-label="revoke token"
                  variant="contained"
                  onClick={() => mutate({})}
                  disabled={isLoading}
                >
                  <Typography variant="button3">REVOKE</Typography>
                </RevokeButton>
              </Grid>
            </Grid>
          </Grid>
        </Grid>
      </ActionDialog>
    </>
  );
};

const EditDescriptionDialog = ({ open, closeDialog, token, setSuccessMessage, setErrorMessage }: DialogProps) => {
  const queryClient = useQueryClient();
  const [description, setDescription] = useState('');
  const [descriptionError, setDescriptionError] = useState<string | false>(false);

  useEffect(() => {
    if (token && token.description) {
      setDescription(token.description.trim());
      setDescriptionError(false);
    }
  }, [token]);

  const [{ isLoading, mutate }] = useMutationPatch(
    [QueryNames.PATCH_USER],
    backendPaths.users_api.REVOKE_TOKEN(token && token.id),
    JSON.stringify({
      description: description?.trim(),
    }),
    {
      onError: (error: any) => {
        if (error.errors.description) {
          setDescriptionError(error.errors.description.map((err: { message: string }) => err.message).join('. '));
        } else {
          setDescriptionError(false);
          setErrorMessage('Token description update failed');
          closeDialog();
        }
      },
      onSuccess: () => {
        closeDialog();
        setSuccessMessage('Token description has been updated');
        queryClient.invalidateQueries([QueryNames.TOKENS]);
      },
    }
  );

  const close = () => !isLoading && closeDialog();

  const submitTokenDescription = () => mutate({});
  const handleDescriptionChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { value } = event.target;
    const trimedValue = value.trim();
    const minCharLength = 2;
    const maxCharLength = 250;

    if (!trimedValue) {
      setDescriptionError('Description is required.');
    } else if (trimedValue.length < minCharLength) {
      setDescriptionError(`Description must be at least ${minCharLength} characters.`);
    } else if (trimedValue.length > maxCharLength) {
      setDescriptionError(`Description can't be more than ${maxCharLength} characters.`);
    } else {
      setDescriptionError(false);
    }

    setDescription(value);
  };

  const isSaveDisabled = isLoading || !!descriptionError || description === token?.description;

  return (
    <>
      <ActionDialog onClose={close} open={open}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Grid container justifyContent="space-between">
              <Grid item>
                <Typography variant="h3">Edit description</Typography>
              </Grid>
              <Grid>
                <CloseDialogButton aria-label="close revoke" onClick={closeDialog} disabled={isLoading} size="large">
                  <CloseIcon color="primary" />
                </CloseDialogButton>
              </Grid>
            </Grid>
          </Grid>
          <Grid item xs={12}>
            <StyledFormControl>
              <TextField
                id="description-input"
                aria-describedby="description-text"
                error={!!descriptionError}
                helperText={descriptionError}
                value={description}
                onChange={handleDescriptionChange}
                inputProps={{ 'aria-label': 'description' }}
              />
            </StyledFormControl>
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
                  aria-label="save token description"
                  variant="contained"
                  onClick={submitTokenDescription}
                  color="primary"
                  disabled={isSaveDisabled}
                >
                  <Typography variant="button3">SAVE</Typography>
                </Button>
              </Grid>
            </Grid>
          </Grid>
        </Grid>
      </ActionDialog>
    </>
  );
};

const UserTokens = () => {
  const { setErrorMessage } = useRequestErrorContext();
  const [showError, toggleShowError] = useState(true);
  const [isOpenRevoke, setIsOpenRevoke] = useState<boolean>(false);
  const [isOpenEdit, setIsOpenEdit] = useState<boolean>(false);
  const [currentToken, setCurrentToken] = useState<Token | null>(null);
  const [actionErrorMessage, setActionErrorMessage] = useState<string | null>(null);
  const [actionSuccessMessage, setActionSuccessMessage] = useState<string | null>(null);
  const [query, updateQuery] = useQueryParams({ sort: StringParam });

  const closeRevoke = () => {
    setIsOpenRevoke(false);
    setCurrentToken(null);
  };
  const closeEdit = () => {
    setIsOpenEdit(false);
    setCurrentToken(null);
  };
  const openRevoke = () => setIsOpenRevoke(true);
  const openEdit = () => setIsOpenEdit(true);
  const handleQueryChange: TableQueryChange = (type, values?) => {
    updateQuery(
      {
        ...values,
      },
      'pushIn'
    );
  };

  let [{ data, isFetching, errorMessage }] = useQueryGet<GetTokensResponse>(
    [QueryNames.TOKENS],
    backendPaths.users_api.GET_TOKENS
  );

  const getBoxColor = useCallback((tokenState: TokenState) => {
    switch (tokenState) {
      case TokenState.ACTIVE:
        return TokenBoxColor.Active;
      case TokenState.EXPIRED:
        return TokenBoxColor.Expired;
      case TokenState.REVOKED:
        return TokenBoxColor.Revoked;
      default:
        return TokenBoxColor.Expired;
    }
  }, []);

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

  // Set sorting values for table
  const order: 'asc' | 'desc' = (query?.sort && (query.sort.charAt(0) === '-' ? 'desc' : 'asc')) || 'desc';
  const orderBy = query?.sort && query.sort.charAt(0) === '-' ? query.sort.slice(1) : query.sort || 'last_seen';
  const sort: TableSort = { order, orderBy };

  const sortedData = data && sortTokens(data, sort);

  const tableData: TableData<Token> = sortedData
    ? sortedData.map(token => ({
        id: token.id,
        description: token,
        permissions: token,
        repository: token,
        lastSeen: token,
        issuedAt: token,
        expiresAt: token,
        revoke: token,
      }))
    : null;

  const tableColumns: TableColumns<Token> = {
    description: {
      sortable: false,
      sortName: null,
      label: 'DESCRIPTION',
      renderValue: token => (
        <DescriptionContainer container alignItems="center">
          <Grid item md={10}>
            {/* eslint-disable-next-line react/destructuring-assignment */}
            <Typography variant="body1">{token.description || 'NA'}</Typography>
          </Grid>
          <Grid item md={2}>
            <StyledIconButton
              aria-label="edit token description"
              size="small"
              onClick={() => {
                setCurrentToken(token);
                openEdit();
              }}
            >
              <Edit color="primary" />
            </StyledIconButton>
          </Grid>
        </DescriptionContainer>
      ),
    },
    permissions: {
      sortable: true,
      sortName: 'state',
      label: 'PERMISSIONS',
      renderValue: ({ state, permissions, id }) => {
        const boxColor = getBoxColor(state);
        return (
          <PermissionContainer container spacing={1}>
            <Grid item md={12}>
              <Grid container>
                <StyledBox backgroundColor={boxColor}>
                  <Grid container alignItems="center" spacing={1}>
                    <StyledTextChipGridItem item state={state}>
                      <TextChip text={state} />
                    </StyledTextChipGridItem>
                    <Grid item>
                      <CustomTooltip title={<TokenTooltipInfo />} placement="top" arrow>
                        <Typography variant="code2">{id}</Typography>
                      </CustomTooltip>
                    </Grid>
                  </Grid>
                </StyledBox>
              </Grid>
            </Grid>
            <PermSecondRow item md={12}>
              <Permissions permissions={permissions} />
            </PermSecondRow>
          </PermissionContainer>
        );
      },
    },
    repository: {
      sortable: false,
      sortName: null,
      label: 'REPOSITORY',
      renderValue: ({ customer, repo }) =>
        customer && repo ? (
          <RepoInfoContainer container>
            <Grid item md={12}>
              <RepoInfoFirstRow variant="body2">
                <StyledLink to={`${paths.builds(customer.slug, repo.slug)}`}>
                  {`${repo.name} (${repo.slug})`}
                </StyledLink>
              </RepoInfoFirstRow>
            </Grid>
            <Grid item md={12}>
              <Typography variant="body2">
                in{' '}
                <StyledLink
                  to={`${paths.organization(customer.slug)}`}
                >{`${customer.name} (${customer.slug})`}</StyledLink>
              </Typography>
            </Grid>
          </RepoInfoContainer>
        ) : (
          <RepoInfoText variant="body2">No repository</RepoInfoText>
        ),
    },
    lastSeen: {
      sortable: true,
      sortName: 'last_seen',
      label: 'LAST SEEN',
      renderValue: ({ last_seen }) => (
        <LastSeenBox>
          <LastTimeMobileLabel variant="caption">Last seen</LastTimeMobileLabel>
          <Typography variant="body2">{last_seen ? utcTimeAgo(last_seen) : 'Unseen'}</Typography>
        </LastSeenBox>
      ),
    },
    issuedAt: {
      sortable: true,
      sortName: 'issued_at',
      label: 'ISSUED AT',
      renderValue: ({ issued_at }) => (
        <LastTimeMobileBox>
          <LastTimeMobileLabel variant="caption">Issued at</LastTimeMobileLabel>
          <Typography variant="body2">{utcTimeAgo(issued_at)}</Typography>
        </LastTimeMobileBox>
      ),
    },
    expiresAt: {
      sortable: true,
      sortName: 'expires_at',
      label: 'EXPIRES AT',
      renderValue: ({ expires_at }) => (
        <LastTimeMobileBox>
          <LastTimeMobileLabel variant="caption">Expires at</LastTimeMobileLabel>
          <Typography variant="body2">{stringToDate(expires_at)}</Typography>
        </LastTimeMobileBox>
      ),
    },
    revoke: {
      sortable: false,
      sortName: null,
      label: '',
      renderValue: token =>
        // eslint-disable-next-line react/destructuring-assignment
        token.can_revoke ? (
          <>
            <RevokeButtonBorder />
            <RevokeButtonContainer>
              <Button
                onClick={() => {
                  setCurrentToken(token);
                  openRevoke();
                }}
              >
                <Typography variant="button3" color="error">
                  REVOKE
                </Typography>
              </Button>
            </RevokeButtonContainer>
          </>
        ) : null,
    },
  };

  const showActionSuccess = actionSuccessMessage && !!actionSuccessMessage.length;
  const showActionError = actionErrorMessage && !!actionErrorMessage.length;

  return (
    <>
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Grid container spacing={1}>
            <Grid item xs={12}>
              <Typography variant="h2">Pants client tokens</Typography>
            </Grid>
            <Grid item xs={12}>
              {data?.max_reached && (
                <Typography variant="body2">You have reached a maximum of {data.max_tokens} active tokens</Typography>
              )}
            </Grid>
          </Grid>
        </Grid>
        <Grid item xs={12}>
          <Table
            name="tokens"
            sort={sort}
            columns={tableColumns}
            data={tableData}
            isLoading={isFetching}
            rowStyles={rowStyles}
            bodyRowStyles={bodyRowStyles}
            onQueryChange={handleQueryChange}
          />
        </Grid>
      </Grid>
      <RevokeDialog
        open={isOpenRevoke}
        closeDialog={closeRevoke}
        token={currentToken}
        setSuccessMessage={setActionSuccessMessage}
        setErrorMessage={setActionErrorMessage}
      />
      <EditDescriptionDialog
        open={isOpenEdit}
        closeDialog={closeEdit}
        token={currentToken}
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

export default UserTokens;
