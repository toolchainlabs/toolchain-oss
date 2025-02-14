/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { Paper } from '@mui/material';
import { styled } from '@mui/material/styles';
import Grid from '@mui/material/Grid';
import { Typography } from '@mui/material';
import { Link } from '@mui/material';

const CardPaper = styled(Paper)(() => ({
  padding: 40,
  maxWidth: 640,
}));

const ExternalLink = styled(Link)(() => ({
  marginLeft: 4,
  [`&:hover`]: {
    textDecoration: 'underline !important',
  },
}));

const AdditionalExplanationCard = () => {
  return (
    <CardPaper elevation={0}>
      <Grid container flexDirection="column" spacing={2}>
        <Grid item>
          <Typography variant="h3">Why is this relevant?</Typography>
        </Grid>
        <Grid item>
          <Typography variant="body1">
            Pants uses static analysis to learn about the structure and
            dependencies of your codebase. That data allows it to apply
            fine-grained caching and concurrency, to speed up builds. It also
            makes that data available for inspection and analysis by users. This
            site uses that data to visualize your codebase as a graph.
          </Typography>
        </Grid>
        <Grid item>
          <Typography variant="subtitle1">
            If you&apos;re interested in learning how Pants can streamline and
            speed up the testing and packaging workflows in your repo, come and
            <ExternalLink
              href="https://www.pantsbuild.org/docs/getting-help"
              type="external"
              target="_blank"
              rel="noopener noreferrer"
            >
              chat with us
            </ExternalLink>
            !
          </Typography>
        </Grid>
      </Grid>
    </CardPaper>
  );
};

export default AdditionalExplanationCard;
