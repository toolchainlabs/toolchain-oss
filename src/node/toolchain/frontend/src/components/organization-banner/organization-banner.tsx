/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import Typography from '@mui/material/Typography';
import Grid from '@mui/material/Grid';
import Paper from '@mui/material/Paper';
import Button from '@mui/material/Button';
import { Link, useParams } from 'react-router-dom';
import { alpha } from '@mui/material/styles';

import { ToolchainLogoHorizontal } from 'assets/icons';
import CustomerStatus from 'common/enums/CustomerStatus';
import paths from 'utils/paths';
import withExternalLink from 'utils/hoc/with-external-link/with-external-link';
import { styled } from '@mui/material/styles';

type OrganizationBannerProps = { status: CustomerStatus | 'noBuilds'; name: string; docsUrl?: string };
type BannerConst = Record<
  CustomerStatus | 'noBuilds',
  {
    text: string;
    color: string;
    buttonText: string;
    ActionLink: ({ children }: { children: JSX.Element }) => JSX.Element;
  }
>;

const StyledImage = styled('img')(() => ({
  display: 'flex',
}));

const OrganizationBanner = ({ status, name, docsUrl }: OrganizationBannerProps) => {
  const { orgSlug } = useParams();
  const BANNER: BannerConst = {
    [CustomerStatus.FREE_TRIAL]: {
      text: `${name} is in free trial. Upgrade to continue using the service at the end of the trial.`,
      color: 'primary',
      buttonText: 'SEE PLANS',
      ActionLink: ({ children }) => (
        <Link to={paths.organization(orgSlug)} style={{ textDecoration: 'none' }}>
          {children}
        </Link>
      ),
    },
    [CustomerStatus.LIMITED]: {
      text: 'The free trial has expired. Upgrade to resume service.',
      color: 'error',
      buttonText: 'UPGRADE',
      ActionLink: ({ children }) => (
        <Link to={paths.organization(orgSlug)} style={{ textDecoration: 'none' }}>
          {children}
        </Link>
      ),
    },
    noBuilds: {
      text: `To start running builds in this repo, please finish the setup.`,
      color: 'warning',
      buttonText: 'INSTRUCTIONS',
      ActionLink: ({ children }) => {
        const Component = withExternalLink(() => children, docsUrl, null);

        return <Component />;
      },
    },
  };

  const { text, color, buttonText, ActionLink } = BANNER[status];

  const StyledPaper = styled(Paper)(({ theme }) => ({
    padding: `${theme.spacing(3.3)} ${theme.spacing(5)}`,
    boxShadow: 'none',
    borderRadius: theme.spacing(1),
    height: '100%',
    width: '100%',
    display: 'flex',
    transition: `box-shadow 3s ${theme.transitions.easing.easeOut}`,
    [`&:hover`]: {
      boxShadow: `0px 0px 40px ${alpha((theme.palette as any)[color].main, 0.5)}`,
    },
  }));

  return (
    <StyledPaper color={color}>
      <Grid container spacing={5} alignItems="center" sx={{ maxHeigth: 88 }}>
        <Grid item mr={5}>
          <StyledImage src={ToolchainLogoHorizontal} alt="Toolchain logo" />
        </Grid>
        <Grid item>
          <Typography variant="body3">{text}</Typography>
        </Grid>
        <Grid item ml="auto">
          <ActionLink>
            <Button variant="contained" color={color as any}>
              <Typography variant="button1" color="white">
                {buttonText}
              </Typography>
            </Button>
          </ActionLink>
        </Grid>
      </Grid>
    </StyledPaper>
  );
};

export default OrganizationBanner;
