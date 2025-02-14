/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { styled } from '@mui/material/styles';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import LearnMore from '../learn-more';

type FooterProps = {
  showPantsInfo?: boolean;
};

const tosUrl = `${window.location.origin}/terms`;

const TOSLink = styled('a')(({ theme }) => ({
  color: theme.palette.text.secondary,
  cursor: 'pointer',
  ['&:hover']: {
    textDecoration: 'underline !important',
  },
}));

const TOSBorder = styled('div')(() => ({
  height: 1,
  width: 40,
  backgroundColor: '#E0E0E0',
}));

const TOSContainer = styled(Grid)(({ theme }) => ({
  marginBottom: theme.spacing(5),
  [theme.breakpoints.down('md')]: {
    marginBottom: theme.spacing(3),
  },
}));

const Footer = ({ showPantsInfo = false }: FooterProps) => {
  const popupPlacement = showPantsInfo ? 'top' : 'bottom-end';
  return (
    <footer>
      {showPantsInfo ? (
        <Grid container flexDirection="column" spacing={2} alignItems="center">
          <Grid item>
            <Grid container spacing={0.5}>
              <Grid item>
                <Typography variant="body1" color="text.secondary">
                  Powered by
                </Typography>
              </Grid>
              <Grid item>
                <Typography variant="subtitle1">Pants Build</Typography>
              </Grid>
            </Grid>
          </Grid>
          <Grid item>
            <svg
              width="35"
              height="63"
              viewBox="0 0 35 63"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M13.5622 63H1.7497L0.285156 13.5625L6.99969 8.75L9.18719 3.5H25.8123L30.1873 10.0625L33.0712 11.559L34.9998 28L17.4997 43.75V30.1875L24.0622 24.5L17.4997 16.1875H14.8748L13.5622 63Z"
                fill="#044EF3"
              />
              <path
                d="M25.8125 3.5H30.6249L33.0714 11.559L30.1875 10.0625L25.8125 3.5Z"
                fill="#91CAFF"
              />
              <path
                d="M0 3.5H9.1875L7 8.75L0.285461 13.5625L0 3.5Z"
                fill="#91CAFF"
              />
              <path d="M0 0.875L30.625 0V2.625H0V0.875Z" fill="#91CAFF" />
            </svg>
          </Grid>
          <Grid item>
            <LearnMore align="center" placement={popupPlacement} />
          </Grid>
        </Grid>
      ) : null}
      <TOSContainer container flexDirection="column" alignItems="center">
        <Grid item mb={1}>
          <TOSBorder />
        </Grid>
        <Grid item>
          <TOSLink href={tosUrl} target="_blank" rel="noopener noreferrer">
            <Typography variant="caption">Terms of Use</Typography>
          </TOSLink>
        </Grid>
      </TOSContainer>
    </footer>
  );
};

export default Footer;
