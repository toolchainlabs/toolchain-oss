/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { useState } from 'react';
import Paper from '@mui/material/Paper';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import MailchimpSubscribe from 'react-mailchimp-subscribe';
import FormControl from '@mui/material/FormControl';
import InputAdornment from '@mui/material/InputAdornment';
import TextField from '@mui/material/TextField';
import EmailIcon from '@mui/icons-material/Email';
import { styled } from '@mui/material/styles';

import Background from '../background/background';
import Footer from '../footer/footer';
import SeeExamplesContainer from '../see-examples-container';

const StyledPaper = styled(Paper)(({ theme }) => ({
  maxWidth: 800,
  boxShadow: 'none',
  background: theme.palette.common.white,
  borderRadius: theme.spacing(1),
  margin: '0 auto',
  padding: 80,
}));

const StyledButton = styled(Button)(({ theme }) => ({
  color: theme.palette.common.white,
  borderTopLeftRadius: 0,
  borderBottomLeftRadius: 0,
  padding: '12px 22px',
  boxShadow: 'none',
}));

const StyledTextField = styled(TextField)(({ theme }) => ({
  ['& .MuiOutlinedInput-root']: {
    borderTopRightRadius: 0,
    borderBottomRightRadius: 0,
    ['& fieldset']: {
      borderColor: theme.palette.primary.main,
    },
  },
}));

const ProcessingFailed = () => {
  const [email, setEmail] = useState<string | null>('');
  const [shouldShowExamples, setShouldShowExamples] = useState<boolean>(false);

  const showExamples = () => setShouldShowExamples(true);
  const hideExamples = () => setShouldShowExamples(false);

  return (
    <MailchimpSubscribe
      url={
        'https://toolchainlabs.us19.list-manage.com/subscribe/post?u=4394020cf030b96d17aaabc83&id=908a6f67bb'
      }
      render={({ subscribe, status, message }) => {
        const isSending = !!status && status === 'sending';
        const succeded = !!status && status === 'success';
        const isError = !!status && status === 'error';
        const submit = () => {
          const trimmedValue = email?.trim();
          if (trimmedValue) subscribe({ EMAIL: trimmedValue });
        };

        const headerText = succeded ? 'Thank you!' : 'Ooops!';
        const paragraph = succeded ? (
          <Typography variant="body3" align="center" component="div">
            We will send updates to {email}.
          </Typography>
        ) : (
          <Typography variant="body3" align="center" component="div">
            We encountered a problem while processing this repo. We&#39;re
            looking <br />
            into it. To receive an update when we have a solution, please
            <br />
            subscribe to our newsletter.
          </Typography>
        );

        return (
          <Background>
            <Grid container spacing={5} justifyContent="center" zIndex={10}>
              <Grid item xs={12}>
                <Grid item xs={12} textAlign="center" mt={8}>
                  <Typography variant="h2" color="text">
                    Graph My Repo
                  </Typography>
                </Grid>
              </Grid>
              {shouldShowExamples ? (
                <Grid item xs={6} zIndex={10}>
                  <SeeExamplesContainer onBackBtnClick={hideExamples} />
                </Grid>
              ) : (
                <Grid item xs={12}>
                  <StyledPaper>
                    <Grid container spacing={3} justifyContent="center">
                      <Grid item xs={12}>
                        <Typography variant="h3" align="center">
                          {headerText}
                        </Typography>
                      </Grid>
                      <Grid item xs={12}>
                        {paragraph}
                      </Grid>
                      {!succeded ? (
                        <Grid item xs={12}>
                          <FormControl
                            variant="standard"
                            sx={{ width: '79.5%' }}
                          >
                            <StyledTextField
                              sx={{
                                borderTopRightRadius: 0,
                                borderBottomRightRadius: 0,
                              }}
                              error={isError}
                              helperText={isError && <>{message}</>}
                              onInput={(
                                event: React.ChangeEvent<HTMLInputElement>
                              ) => setEmail(event.target.value)}
                              value={email}
                              InputProps={{
                                placeholder: 'Email',
                                startAdornment: (
                                  <InputAdornment position="start">
                                    <EmailIcon color="primary" />
                                  </InputAdornment>
                                ),
                              }}
                            />
                          </FormControl>
                          <StyledButton
                            variant="contained"
                            color="primary"
                            onClick={submit}
                            disabled={isSending}
                          >
                            <Typography variant="button3">NOTIFY ME</Typography>
                          </StyledButton>
                        </Grid>
                      ) : (
                        <Grid item xs={12} textAlign="center">
                          <Button
                            variant="contained"
                            color="primary"
                            onClick={showExamples}
                          >
                            <Typography variant="button3">
                              SEE EXAMPLE REPOS
                            </Typography>
                          </Button>
                        </Grid>
                      )}
                    </Grid>
                  </StyledPaper>
                </Grid>
              )}
            </Grid>
            <Grid item xs={12}>
              <Footer showPantsInfo={true} />
            </Grid>
          </Background>
        );
      }}
    />
  );
};

export default ProcessingFailed;
