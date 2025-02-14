/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import Grid from '@mui/material/Grid';
import { styled } from '@mui/material/styles';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import ShareIcon from '@mui/icons-material/Share';

import LearnMore from './learn-more';
import theme from '../theme';
type HeaderProps = { copyToClipboard: () => void };

const HeaderContainer = styled(Grid)(({ theme }) => ({
  position: 'absolute',
  top: 40,
  margin: 0,
  width: `100%`,
  zIndex: 10,
  paddingLeft: 40,
  paddingRight: 40,
  [theme.breakpoints.down('md')]: {
    display: 'none',
  },
}));
const StyledShare = styled(ShareIcon)(() => ({
  color: theme.palette.primary.light,
}));

const StyledBack = styled(ArrowBackIcon)(() => ({
  color: theme.palette.primary.light,
}));

const goBackUrl = window.location.origin;

const Header = ({ copyToClipboard }: HeaderProps) => {
  return (
    <HeaderContainer container justifyContent="space-between">
      <Grid item>
        <Grid container alignItems="center" spacing={1}>
          <Grid item>
            <IconButton color="primary" aria-label="go back" href={goBackUrl}>
              <StyledBack />
            </IconButton>
          </Grid>
          <Grid item textAlign="center">
            <IconButton
              color="primary"
              onClick={copyToClipboard}
              aria-label="copy link"
            >
              <StyledShare />
            </IconButton>
          </Grid>
        </Grid>
      </Grid>
      <Grid item>
        <Grid
          container
          flexDirection="column"
          spacing={2}
          alignItems="flex-end"
        >
          <Grid item>
            <Grid container spacing={0.5}>
              <Grid item>
                <Typography
                  variant="body1"
                  color={theme.palette.text.secondary}
                >
                  Powered by
                </Typography>
              </Grid>
              <Grid item>
                <Typography variant="subtitle1">Pants Build</Typography>
              </Grid>
            </Grid>
          </Grid>
          <Grid item>
            <LearnMore align="flex-end" />
          </Grid>
        </Grid>
      </Grid>
    </HeaderContainer>
  );
};

export default Header;
