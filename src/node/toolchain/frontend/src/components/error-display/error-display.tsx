/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import Grid from '@mui/material/Grid';
import Container from '@mui/material/Container';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Snackbar from '@mui/material/Snackbar';
import IconButton from '@mui/material/IconButton';
import CloseIcon from '@mui/icons-material/Close';
import { styled } from '@mui/material/styles';

import { ToolchainLogoVertical } from 'assets/icons';

type ErrorDisplayProps = {
  buttonText: string;
  title: string;
  description?: string;
  errorId?: string;
  goBackUrl?: string;
};

const StyledGridBackground = styled(Grid)(({ theme }) => ({
  height: '100vh',
  backgroundColor: theme.palette.grey[100],
}));
const StyledGridContainer = styled(Grid)(({ theme }) => ({
  padding: theme.spacing(10),
  backgroundColor: 'white',
  [theme.breakpoints.down('md')]: {
    padding: `${theme.spacing(5)} ${theme.spacing(2)}`,
  },
}));
const StyledLogoWithName = styled('img')(({ theme }) => ({
  width: 200,
  height: 131,
  [theme.breakpoints.down('md')]: {
    width: 160,
    height: 104,
  },
}));
const StyledErrorStatus = styled('div')(({ theme }) => ({
  backgroundColor: 'rgba(0, 169, 183, 0.08)',
  borderRadius: '140px',
  width: 174,
  height: 174,
  margin: 'auto',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  color: theme.palette.primary.main,
  [theme.breakpoints.down('md')]: {
    width: 160,
    height: 160,
  },
}));
const StyledButton = styled(Button)(({ theme }) => ({
  backgroundColor: theme.palette.primary.main,
  color: theme.palette.primary.contrastText,
  '&:hover': {
    backgroundColor: theme.palette.primary.dark,
  },
}));
const StyledAnchorEmail = styled('a')(({ theme }) => ({
  color: theme.palette.primary.main,
}));
const StyledDivErrorId = styled('span')(({ theme }) => ({
  color: theme.palette.primary.main,
  cursor: 'pointer',
}));

const ErrorDisplay = ({ buttonText, title, description = '', errorId, goBackUrl = '/' }: ErrorDisplayProps) => {
  const navigate = useNavigate();
  const [showCopyMessage, setShowCopyMessage] = useState<boolean>(false);

  const copyToClipboard = (text: string) => navigator.clipboard.writeText(text);

  const onRequestIdClickHandler = () => {
    copyToClipboard(errorId);
    setShowCopyMessage(true);
  };

  const mailToAdress = `mailto:support@toolchain.com?subject=${title}${errorId ? `. Request id: ${errorId}` : ''}`;

  const renderDescription = (
    <>
      {description} If it persists, please contact{' '}
      <StyledAnchorEmail href={mailToAdress}>support@toolchain.com</StyledAnchorEmail>
      {errorId ? (
        <>
          {' '}
          and pass along the ID: <StyledDivErrorId onClick={onRequestIdClickHandler}>{errorId}</StyledDivErrorId>
        </>
      ) : (
        ''
      )}
    </>
  );

  return (
    <Container>
      <StyledGridBackground container justifyContent="center" alignContent="center">
        <StyledGridContainer item xs={12} md={6}>
          <Grid container spacing={5} direction="column">
            <Grid item>
              <Grid container alignItems="center" spacing={2} direction="column">
                <Grid item>
                  <StyledLogoWithName src={ToolchainLogoVertical} alt="Toolchain logo" />
                </Grid>
                <Grid item>
                  <Typography variant="subtitle1">The distributed software build system</Typography>
                </Grid>
              </Grid>
            </Grid>
            <Grid item>
              <Grid container alignItems="center" spacing={3} direction="column">
                <Grid item>
                  <StyledErrorStatus>
                    <Typography variant="h2">oops...</Typography>
                  </StyledErrorStatus>
                </Grid>
                <Grid item>
                  <Grid container spacing={1} direction="column" alignItems="center">
                    <Grid item>
                      <Typography variant="subtitle1">{title}</Typography>
                    </Grid>
                    {description ? (
                      <Grid item>
                        <Typography variant="body1" textAlign="center">
                          {renderDescription}
                        </Typography>
                      </Grid>
                    ) : null}
                  </Grid>
                </Grid>
                <Grid item>
                  <StyledButton variant="contained" size="large" onClick={() => navigate(goBackUrl, { replace: true })}>
                    {buttonText}
                  </StyledButton>
                </Grid>
              </Grid>
            </Grid>
          </Grid>
        </StyledGridContainer>
      </StyledGridBackground>
      <Snackbar
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        autoHideDuration={5000}
        open={showCopyMessage}
        onClose={() => setShowCopyMessage(false)}
        message="The ID has been copied"
        action={
          <IconButton size="small" aria-label="close" color="inherit" onClick={() => setShowCopyMessage(false)}>
            <CloseIcon />
          </IconButton>
        }
      />
    </Container>
  );
};

export default ErrorDisplay;
