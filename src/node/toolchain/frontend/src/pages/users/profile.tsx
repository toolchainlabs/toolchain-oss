/*
Copyright 2019 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useTheme } from '@mui/material/styles';
import LinearProgress from '@mui/material/LinearProgress';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Snackbar from '@mui/material/Snackbar';
import Button from '@mui/material/Button';
import FormControl from '@mui/material/FormControl';
import IconButton from '@mui/material/IconButton';
import Close from '@mui/icons-material/Close';
import Edit from '@mui/icons-material/Edit';
import MuiAlert from '@mui/material/Alert';
import TextField from '@mui/material/TextField';
import Select, { SelectChangeEvent } from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import FormHelperText from '@mui/material/FormHelperText';
import SnackbarContent from '@mui/material/SnackbarContent';
import useMediaQuery from '@mui/material/useMediaQuery';
import { styled } from '@mui/material/styles';

import UserAvatar from 'components/users/user-avatar';
import { useUserContext } from 'store/user-store';
import backendPaths from 'utils/backend-paths';
import generateUrl from 'utils/url';
import { getHost } from 'utils/init-data';
import { useQueryGet, useMutationPatch } from 'utils/hooks/query';
import QueryNames from 'common/enums/QueryNames';
import { ToolchainUser } from 'common/interfaces/builds-options';

const StyledGridContainer = styled(Grid)(({ theme }) => ({
  height: '90vh',
  alignItems: 'center',
  [theme.breakpoints.down('md')]: {
    alignItems: 'flex-start',
  },
}));

const StyledMenuTypography = styled(Typography)(() => ({
  width: '100%',
  maxWidth: 620,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
}));

const StyledBox = styled(Box)(({ theme }) => ({
  maxWidth: 430,
  padding: theme.spacing(5),
  backgroundColor: theme.palette.common.white,
  borderRadius: theme.spacing(1),
  margin: 'auto',
  [theme.breakpoints.down('md')]: {
    maxWidth: 'unset',
  },
}));

const StyledTypographyBreakAnywhere = styled(Typography)(() => ({ lineBreak: 'anywhere' }));

const UserProfile = () => {
  const { user } = useUserContext();
  const queryClient = useQueryClient();
  const { avatar_url: avatarUrl, username, full_name: fullname, email: userEmail, api_id: apiId } = user || {};
  const minCharLength = 5;
  const maxCharLength = 150;
  // Snackbars
  const [openSuccess, setOpenSuccess] = useState<boolean>(false);
  const [openError, setOpenError] = useState<boolean>(false);

  // Form controls
  const [userName, setUsername] = useState(username);
  const [fullName, setFullName] = useState(fullname);
  const [email, setEmail] = useState(userEmail || '');
  const [userNameError, setUserNameError] = useState<string | false>(null);
  const [fullNameError, setFullNameError] = useState<string | false>(null);
  const [emailError, setEmailError] = useState<string | false>(null);

  // Editing state
  const [isEditingUsername, setIsEditingUsername] = useState(false);
  const [isEditingFullName, setIsEditingFullName] = useState(false);
  const [isChangingEmail, setIsChangingEmail] = useState(false);

  const theme = useTheme();
  const isMobileScreen = useMediaQuery(theme.breakpoints.down('md'));

  const [{ data: emailData, isFetching }] = useQueryGet<{ emails: string[] }>(
    [QueryNames.EMAILS],
    backendPaths.users_api.EMAILS,
    null
  );

  const [{ isLoading, mutate }] = useMutationPatch(
    [QueryNames.PATCH_USER],
    backendPaths.users_api.PATCH_USER(apiId),
    JSON.stringify({
      username: userName?.trim(),
      full_name: fullName?.trim(),
      email,
    }),
    {
      onError: (error: any) => {
        if (error.full_name) {
          setFullNameError(error.full_name.join(' '));
        } else {
          setFullNameError(false);
        }

        if (error.username) {
          setUserNameError(error.username.join(' '));
        } else {
          setUserNameError(false);
        }

        if (error.email) {
          setEmailError(error.email.join(' '));
        } else {
          setEmailError(false);
        }

        if (!error.full_name && !error.username && !error.email) {
          setOpenError(true);
        }
      },
      onSuccess: (data: ToolchainUser) => {
        setFullNameError(null);
        setUserNameError(null);
        setEmailError(null);
        setIsEditingFullName(false);
        setIsEditingUsername(false);
        setIsChangingEmail(false);
        setOpenSuccess(true);
        queryClient.setQueryData([QueryNames.ME], () => data);
      },
    }
  );

  const handleEmailChange = (event: SelectChangeEvent<string>) => {
    const { value } = event.target;

    if (value !== email) {
      setIsChangingEmail(true);
      setEmail(value as string);
    }
  };

  const handleUserNameChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { value } = event.target;
    const trimmedValue = value.trim();

    if (!trimmedValue) {
      setUserNameError('Username is required.');
    } else if (trimmedValue.length < minCharLength) {
      setUserNameError(`Username must be at least ${minCharLength} characters.`);
    } else if (trimmedValue.length > maxCharLength) {
      setUserNameError(`Username can't be more than ${maxCharLength} characters.`);
    } else {
      setUserNameError(false);
    }

    if (value !== userName) {
      setIsEditingUsername(true);
      setUsername(value);
    }
  };

  const handleFullNameChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { value } = event.target;
    const trimmedValue = value.trim();

    if (!trimmedValue) {
      setFullNameError('Name is required.');
    } else if (trimmedValue.length < minCharLength) {
      setFullNameError(`Name must be at least ${minCharLength} characters.`);
    } else if (trimmedValue.length > maxCharLength) {
      setFullNameError(`Name can't be more than ${maxCharLength} characters.`);
    } else {
      setFullNameError(false);
    }

    if (value !== fullName) {
      setIsEditingFullName(true);
      setFullName(value);
    }
  };

  useEffect(() => {
    if (user) {
      setUsername(user.username);
      setEmail(user.email);
      setFullName(user.full_name);
    }
  }, [user]);

  if (!user || isFetching) {
    return <LinearProgress />;
  }

  const isFormActive = isEditingUsername || isEditingFullName || isChangingEmail;

  const Actions = () => {
    const cancelEdit = () => {
      if (isEditingUsername) {
        setUsername(username);
        setIsEditingUsername(false);
        setUserNameError(null);
      }

      if (isEditingFullName) {
        setFullName(fullname);
        setIsEditingFullName(false);
        setFullNameError(null);
      }

      if (isChangingEmail) {
        setEmail(userEmail);
        setIsChangingEmail(false);
        setEmailError(null);
      }
    };
    const signOut = () => window.location.assign(generateUrl(backendPaths.users_ui.LOGOUT, getHost()));
    const submitUserForm = () => mutate({});

    const hasError = !!userNameError || !!fullNameError;
    const isSaveDisabled = isLoading || hasError;

    return isFormActive ? (
      <Grid container spacing={5} justifyContent="flex-end" alignItems="center">
        <Grid item>
          <Button variant="text" size="medium" onClick={cancelEdit}>
            <Typography variant="button1" color="primary">
              CANCEL
            </Typography>
          </Button>
        </Grid>
        <Grid item>
          <Button variant="contained" color="primary" size="medium" onClick={submitUserForm} disabled={isSaveDisabled}>
            <Typography variant="button1">SAVE</Typography>
          </Button>
        </Grid>
      </Grid>
    ) : (
      <Grid container justifyContent="center" alignItems="center">
        <Grid item>
          <Button variant="text" size="small" onClick={signOut}>
            <Typography variant="button2" color="error">
              SIGN OUT
            </Typography>
          </Button>
        </Grid>
      </Grid>
    );
  };

  const hasMultipleEmails = emailData.emails.length > 1;
  const emailText = hasMultipleEmails
    ? 'All verified email addresses come from your login provider. We will use this email address for account maintenance messages.'
    : 'The verified email address comes from your login provider. We will use this email address for account maintenance messages.';

  const NameComponent = isMobileScreen ? StyledTypographyBreakAnywhere : Typography;
  const nameVariant = isMobileScreen ? 'body3' : 'body2';

  return (
    <>
      <StyledGridContainer container justifyContent="center">
        <Grid item xs={12}>
          <StyledBox>
            <Grid container alignItems="center" justifyContent="center" spacing={3}>
              <Grid item xs={12}>
                <Grid container spacing={1}>
                  <Grid item xs={12}>
                    <UserAvatar url={avatarUrl} size="large" userFullName={fullname || username} />
                  </Grid>
                  <Grid item xs={12}>
                    {isEditingUsername ? (
                      <FormControl fullWidth>
                        <TextField
                          id="username-input"
                          aria-describedby="username-text"
                          error={!!userNameError}
                          helperText={userNameError}
                          defaultValue={username}
                          onChange={handleUserNameChange}
                          inputProps={{ 'aria-label': 'username' }}
                        />
                      </FormControl>
                    ) : (
                      <Grid container spacing={2}>
                        <Grid item xs={12}>
                          <StyledTypographyBreakAnywhere variant="h2" color="textPrimary" align="center">
                            {username}
                            <IconButton
                              aria-label="edit username"
                              onClick={() => setIsEditingUsername(true)}
                              size="large"
                            >
                              <Edit color="primary" />
                            </IconButton>
                          </StyledTypographyBreakAnywhere>
                        </Grid>
                      </Grid>
                    )}
                  </Grid>
                </Grid>
              </Grid>
              <Grid item xs={12}>
                <Grid container spacing={1}>
                  <Grid item xs={12}>
                    <Typography variant="overline" color="text.disabled">
                      NAME
                    </Typography>
                  </Grid>
                  <Grid item xs={12}>
                    {isEditingFullName ? (
                      <FormControl fullWidth>
                        <TextField
                          id="fullname-input"
                          aria-describedby="fullname-text"
                          error={!!fullNameError}
                          helperText={fullNameError}
                          defaultValue={fullname}
                          onChange={handleFullNameChange}
                          inputProps={{ 'aria-label': 'fullname' }}
                        />
                      </FormControl>
                    ) : (
                      <Grid container justifyContent="space-between" alignItems="center">
                        <Grid item>
                          <NameComponent variant={nameVariant}>{fullname || 'No name specified'}</NameComponent>
                        </Grid>
                        <Grid item ml="auto">
                          <IconButton
                            aria-label="edit full name"
                            onClick={() => setIsEditingFullName(true)}
                            size="large"
                          >
                            <Edit color="primary" fontSize="small" />
                          </IconButton>
                        </Grid>
                      </Grid>
                    )}
                  </Grid>
                </Grid>
              </Grid>
              <Grid item xs={12}>
                <Grid container spacing={1}>
                  <Grid item xs={12}>
                    <Typography variant="overline" color="text.disabled">
                      PRIMARY EMAIL
                    </Typography>
                  </Grid>
                  <Grid item xs={12}>
                    {hasMultipleEmails ? (
                      <FormControl fullWidth variant="outlined" error={!!emailError}>
                        <Select
                          value={email}
                          onChange={handleEmailChange}
                          fullWidth
                          role="combobox"
                          variant="outlined"
                          inputProps={{
                            width: '100%',
                          }}
                        >
                          {/* eslint-disable-next-line @typescript-eslint/no-shadow */}
                          {emailData.emails.map(email => (
                            <MenuItem key={email} value={email}>
                              <StyledMenuTypography variant="body1">{email}</StyledMenuTypography>
                            </MenuItem>
                          ))}
                        </Select>
                        <FormHelperText>{emailError}</FormHelperText>
                      </FormControl>
                    ) : (
                      <StyledTypographyBreakAnywhere key={email} variant="body3">
                        {email}
                      </StyledTypographyBreakAnywhere>
                    )}
                  </Grid>
                  <Grid item xs={12}>
                    <Typography variant="caption" color="text.disabled">
                      {emailText}
                    </Typography>
                  </Grid>
                </Grid>
              </Grid>
              <Grid item xs={12}>
                <Actions />
              </Grid>
            </Grid>
          </StyledBox>
        </Grid>
      </StyledGridContainer>
      <Snackbar
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        autoHideDuration={5000}
        open={openSuccess}
        onClose={() => setOpenSuccess(false)}
      >
        <SnackbarContent
          message="Your profile change has been saved"
          action={
            <IconButton size="small" aria-label="close" color="inherit" onClick={() => setOpenSuccess(false)}>
              <Close />
            </IconButton>
          }
        />
      </Snackbar>
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
    </>
  );
};

export default UserProfile;
