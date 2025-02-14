/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { forwardRef } from 'react';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import Card from '@mui/material/Card';
import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import LinkIcon from '@mui/icons-material/Link';
import ComputerIcon from '@mui/icons-material/Computer';
import FilterDramaIcon from '@mui/icons-material/FilterDrama';
import ContentPasteSearchIcon from '@mui/icons-material/ContentPasteSearch';
import { styled } from '@mui/material/styles';

import OutcomeType from 'common/enums/OutcomeType';
import { BuildOutcome } from 'components/icons/build-outcome';
import { Artifact, AllArtifactContents, EnvName } from 'common/interfaces/build-artifacts';

type ArifactCardProps = {
  description?: string;
  outcome?: OutcomeType;
  hideAllHeaders?: boolean;
  hideBody?: boolean;
  showOutcome?: boolean;
  duration?: string;
  children: JSX.Element;
  hasDirectLinkButton?: boolean;
  artifact?: Artifact<AllArtifactContents>;
  onDirectLinkButtonClick?: (event: React.MouseEvent<HTMLElement>) => void;
};

type TimingsProps = Pick<ArifactCardProps, 'artifact'>;
type TooltipTextObject = { [key in EnvName]: string };
type TimingsTooltipProps = { fromCache: boolean; runTime: string; envName: EnvName };

const StyledCard = styled(Card)(({ theme }) => ({
  padding: theme.spacing(3),
  marginBottom: theme.spacing(3),
  borderRadius: theme.spacing(1),
}));

const StyledTypography = styled(Typography)(() => ({
  wordBreak: 'break-word',
}));

const StyledCachingIndicatorBox = styled(Box)(({ theme }) => ({
  display: 'flex',
  gap: 4,
  alignItems: 'center',
  backgroundColor: 'rgba(0, 169, 183, 0.08)',
  borderRadius: theme.spacing(0.5),
  padding: `0 6px`,
  maxHeight: 18,
  minHeight: 18,
}));

const StyledFromRemoteIcon = styled(FilterDramaIcon)(() => ({
  fontSize: 12,
  alignSelf: 'center',
}));

const StyledDivWithCursor = styled('div')(() => ({
  cursor: 'pointer',
}));

const StyledFromLocalIcon = StyledFromRemoteIcon.withComponent(ComputerIcon);

const StyledFromCacheIcon = StyledFromRemoteIcon.withComponent(ContentPasteSearchIcon);

const TimingsTooltip = ({ envName, fromCache, runTime }: TimingsTooltipProps) => {
  const noCacheText: TooltipTextObject = {
    [EnvName.REMOTE]: 'This ran on a remote worker.',
    [EnvName.LOCAL]: 'This ran on a local machine.',
  };
  const cacheText: TooltipTextObject = {
    [EnvName.REMOTE]: 'This result was fetched from the Toolchain remote cache.',
    [EnvName.LOCAL]: 'This result was fetched from the local cache.',
  };
  const envIcon = {
    [EnvName.REMOTE]: <StyledFromRemoteIcon color="primary" />,
    [EnvName.LOCAL]: <StyledFromLocalIcon color="primary" />,
  };
  const title = fromCache ? cacheText[envName] : noCacheText[envName];

  const env = envIcon[envName];

  return (
    <Tooltip title={title} arrow placement="bottom-end">
      <StyledDivWithCursor>
        <StyledDivWithCursor>
          <StyledCachingIndicatorBox>
            {fromCache ? (
              <StyledFromCacheIcon color="primary" />
            ) : (
              <Typography variant="caption" color="primary.dark">
                {runTime}
              </Typography>
            )}
            {env}
          </StyledCachingIndicatorBox>
        </StyledDivWithCursor>
      </StyledDivWithCursor>
    </Tooltip>
  );
};

const Timings = ({ artifact }: TimingsProps) => {
  const getToDecimalNonRoundedValue = (value: number) => (value / 1000).toFixed(3).slice(0, -1);
  const runTime = `${getToDecimalNonRoundedValue(artifact.timing_msec.run_time)}s`;
  const envName = artifact.env_name;
  const fromCache = artifact.from_cache;

  return [EnvName.LOCAL, EnvName.REMOTE].includes(envName as EnvName) ? (
    <TimingsTooltip envName={envName as EnvName} runTime={runTime} fromCache={fromCache} />
  ) : (
    <StyledCachingIndicatorBox>
      <Typography variant="caption" color="primary.dark">
        {runTime}
      </Typography>
      {envName?.length > 1 ? <Typography variant="caption" color="primary">{`| ${envName}`}</Typography> : null}
    </StyledCachingIndicatorBox>
  );
};

const ArtifactCard = forwardRef((props: ArifactCardProps, ref) => {
  const {
    description,
    outcome,
    hideAllHeaders = false,
    hideBody = false,
    showOutcome = false,
    children,
    duration,
    hasDirectLinkButton = false,
    onDirectLinkButtonClick,
    artifact,
  } = props;
  const hasDuration = Boolean(duration);
  const hasTimings = !!artifact?.timing_msec;

  return (
    <StyledCard elevation={0} ref={ref as any}>
      <Grid container spacing={2}>
        {!hideAllHeaders && (
          <Grid item xs={12}>
            <Grid container spacing={2} alignItems="center" wrap="nowrap">
              {showOutcome ? (
                <Grid item>
                  <BuildOutcome outcome={outcome} chipVariant="noborder" />
                </Grid>
              ) : null}
              <Grid item marginRight="auto" alignSelf="center">
                <StyledTypography variant="subtitle1">{description}</StyledTypography>
              </Grid>
              {hasDuration ? (
                <Grid item>
                  <StyledCachingIndicatorBox>
                    <Typography variant="caption" color="primary" data-testid="timing">
                      {duration}
                    </Typography>
                  </StyledCachingIndicatorBox>
                </Grid>
              ) : null}
              {hasTimings ? (
                <Grid item>
                  <Timings artifact={artifact} />
                </Grid>
              ) : null}
              {hasDirectLinkButton && (
                <Grid item>
                  <IconButton
                    onClick={onDirectLinkButtonClick}
                    aria-label="Copy direct link"
                    size="large"
                    color="primary"
                  >
                    <LinkIcon color="primary" />
                  </IconButton>
                </Grid>
              )}
            </Grid>
          </Grid>
        )}
        {!hideBody && (
          <Grid item xs={12}>
            {children}
          </Grid>
        )}
      </Grid>
    </StyledCard>
  );
});

export default ArtifactCard;
