/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { styled } from '@mui/material/styles';
import Grid from '@mui/material/Grid';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import Tooltip from '@mui/material/Tooltip';

type LearnMoreProps = {
  align: 'flex-end' | 'center';
  placement?: 'bottom-end' | 'top';
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ToBeStyledTooltip = ({ className, ...props }: any) => (
  <Tooltip {...props} classes={{ tooltip: className }} width={400} />
);
const StyledTooltip = styled(ToBeStyledTooltip)(() => ({
  backgroundColor: 'rgba(33, 43, 64, 1)',
  padding: 24,
  maxWidth: 400,
}));

const StyledTitle = styled(Typography)(({ theme }) => ({
  fontWeight: 500,
  fontSize: 16,
  lineHeight: 1.5,
  color: theme.palette.primary.light,
}));

const StyledLink = styled('a')(({ theme }) => ({
  color: theme.palette.primary.light,
  cursor: 'pointer',
  marginLeft: 4,
  marginRight: 4,
  ['&:hover']: {
    textDecoration: 'underline !important',
  },
}));

const StyledLinkBeginning = styled(StyledLink)(() => ({
  marginLeft: 0,
}));

const pantsUrl = 'https://www.pantsbuild.org/';
const toolchainUrl = 'https://www.toolchain.com/';
const contactUsUrl = 'mailto:info@toolchain.com';

const TooltipToolchain = () => (
  <Grid container flexDirection="column" spacing={3}>
    <Grid item>
      <StyledTitle>What is Toolchain?</StyledTitle>
    </Grid>
    <Grid item>
      <Typography variant="body1">
        <StyledLink
          href={toolchainUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          Toolchain
        </StyledLink>
        provides technology, support, and expertise for scalable software
        builds. Toolchain is the lead sponsor of the
        <StyledLink href={pantsUrl} target="_blank" rel="noopener noreferrer">
          Pants
        </StyledLink>
        open source build system.
        <br />
        <StyledLinkBeginning
          href={contactUsUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          Contact us
        </StyledLinkBeginning>
        to learn more about how we can help make your developers&apos; workflows
        fast, stable and secure.
      </Typography>
    </Grid>
  </Grid>
);

const TooltipPants = () => (
  <Grid container flexDirection="column" spacing={3}>
    <Grid item>
      <StyledTitle>What is Pants?</StyledTitle>
    </Grid>
    <Grid item>
      <Typography variant="body1">
        <StyledLink href={pantsUrl} target="_blank" rel="noopener noreferrer">
          Pants
        </StyledLink>
        is an open-source build system with a strong focus on Python, JVM and
        Go. Pants uses static analysis to learn about the structure and
        dependencies of your codebase, and applies this data to speed up your
        builds via fine-grained caching and concurrency. Pants&apos;s static
        analysis provides the data that powers this site!
        <br />
        <StyledLinkBeginning
          href={contactUsUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          Contact us
        </StyledLinkBeginning>
        to learn more about what Pants can do for you.
      </Typography>
    </Grid>
  </Grid>
);

const LearnMore = ({ align, placement = 'bottom-end' }: LearnMoreProps) => {
  return (
    <Grid container spacing={0.25} flexDirection="column" alignItems={align}>
      <Grid item>
        <StyledTooltip title={<TooltipPants />} placement={placement} arrow>
          <Button color="primary">
            <Typography variant="body2" color="primary" textTransform="none">
              What is Pants?
            </Typography>
          </Button>
        </StyledTooltip>
      </Grid>
      <Grid item>
        <StyledTooltip title={<TooltipToolchain />} placement={placement} arrow>
          <Button color="primary">
            <Typography variant="body2" color="primary" textTransform="none">
              What is Toolchain?
            </Typography>
          </Button>
        </StyledTooltip>
      </Grid>
    </Grid>
  );
};

export default LearnMore;
