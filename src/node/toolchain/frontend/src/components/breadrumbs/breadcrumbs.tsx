/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import Breadcrumbs from '@mui/material/Breadcrumbs';
import { Link } from 'react-router-dom';
import Typography from '@mui/material/Typography';
import ChevronRight from '@mui/icons-material/ChevronRight';
import Grid from '@mui/material/Grid';
import paths from 'utils/paths';
import { styled } from '@mui/material/styles';

type BreadrumbsProps = {
  org: string;
  repo?: string;
};

const StyledChevronRight = styled(ChevronRight)(({ theme }) => ({ color: theme.palette.text.secondary, margin: 5 }));
const StyledText = styled(Typography)(({ theme }) => ({ color: theme.palette.text.secondary }));

const BreadCrumbs = ({ org, repo }: BreadrumbsProps) => {
  const BreadcrumbText = ({ text }: { text: string }) => (
    <Grid container justifyContent="center" alignItems="center">
      <StyledText variant="body1">{text.charAt(0).toUpperCase() + text.slice(1)}</StyledText>
      <StyledChevronRight />
    </Grid>
  );

  return (
    <Breadcrumbs separator={null} aria-label="breadcrumb">
      <Grid container justifyContent="center" alignItems="center">
        <Grid item>
          <Link color="inherit" to={paths.organization(org)}>
            <BreadcrumbText text={org} />
          </Link>
        </Grid>
        <Grid item>
          {repo && (
            <Link color="inherit" to={`${paths.builds(org, repo)}?user=me`}>
              <BreadcrumbText text={repo} />
            </Link>
          )}
        </Grid>
      </Grid>
    </Breadcrumbs>
  );
};

export default BreadCrumbs;
