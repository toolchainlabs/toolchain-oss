/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import Typography from '@mui/material/Typography';
import Grid from '@mui/material/Grid';
import { getMillisecondsHumanized } from 'utils/datetime-formats';
import Box from '@mui/material/Box';
import DnsIcon from '@mui/icons-material/Dns';
import TimelapseIcon from '@mui/icons-material/Timelapse';
import Tooltip from '@mui/material/Tooltip';
import { Build } from 'common/interfaces/builds';
import { styled } from '@mui/material/styles';

type NoIndicatorsProps = { loading: boolean };
type CacheIndicatorsProps = Pick<Build, 'indicators'> & { displayTimeSaved?: boolean } & NoIndicatorsProps;
type IndicatorsProps = Pick<CacheIndicatorsProps, 'indicators' | 'displayTimeSaved'>;
type HitRateTooltipProps = {
  hitRate: string;
  hitRateLocal: string;
  hitRateRemote: string;
  children: React.ReactElement<any, any>;
};
type TimeSavedTooltipProps = {
  totalTimeSaved: string;
  localTimeSaved: string;
  remoteTimeSaved: string;
  children: React.ReactElement<any, any>;
};

const Polygon = styled(Box)(() => ({
  height: 22,
  width: 26,
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  clipPath: 'polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%)',
  backgroundColor: '#1C2B39',
  transform: 'rotate(90deg)',
}));

const InvertedPolygon = styled(Polygon)(({ theme }) => ({
  backgroundColor: theme.palette.primary.light,
}));

const GreyPolygon = styled(Polygon)(({ theme }) => ({
  backgroundColor: theme.palette.grey[800],
}));

const LightTypography = styled(Typography)(({ theme }) => ({
  color: theme.palette.primary.light,
}));

const PolygonTimelapseIcon = styled(TimelapseIcon)(({ theme }) => ({
  fontSize: 14,
  color: theme.palette.primary.light,
  transform: 'rotate(280deg)',
}));

const PolygonTimelapseDarkIcon = styled(PolygonTimelapseIcon)(() => ({
  color: '#1C2B39',
}));

const PolygonDnsIcon = styled(DnsIcon)(({ theme }) => ({
  fontSize: 14,
  color: theme.palette.primary.light,
  transform: 'rotate(-90deg)',
}));

const PolygonDnsGreyIcon = styled(PolygonDnsIcon)(({ theme }) => ({
  color: theme.palette.grey[300],
}));

const PolygonDnsDarkIcon = styled(PolygonDnsIcon)(() => ({
  color: '#1C2B39',
}));

const TextMarginLeft = styled(Typography)(() => ({
  marginLeft: 5,
}));

const GridNoMargin = styled(Grid)(() => ({
  margin: 0,
}));

const CacheInfoText = styled(Typography)(({ theme }) => ({
  color: theme.palette.primary.dark,
}));

const ColorMediumGray = styled(Typography)(({ theme }) => ({
  color: theme.palette.grey[600],
}));

const CacheWrapper = styled(Box)(({ theme }) => ({
  marginLeft: -16,
  padding: `0px ${theme.spacing(1)} 0px 10px`,
  backgroundColor: 'rgba(0, 169, 183, 0.08)',
  borderRadius: '0px 2px 2px 0px',
  maxHeight: 18,
  display: 'flex',
  alignItems: 'center',
}));

const CacheWrapperGrey = styled(CacheWrapper)(({ theme }) => ({
  backgroundColor: theme.palette.grey[300],
}));

const TimeSavedTooltip = ({ totalTimeSaved, localTimeSaved, remoteTimeSaved, children }: TimeSavedTooltipProps) => {
  const timeSavedTooltip = (
    <Grid container spacing={2}>
      <Grid item>
        <Grid container spacing={1}>
          <Grid item>
            <InvertedPolygon>
              <PolygonTimelapseDarkIcon />
            </InvertedPolygon>
          </Grid>
          <Grid item>
            <LightTypography variant="subtitle2">{`${totalTimeSaved} CPU time saved`}</LightTypography>
          </Grid>
        </Grid>
      </Grid>
      <Grid item>
        <Grid container>
          <Grid item>
            <Typography variant="caption">{`${totalTimeSaved} of cpu time was saved in this build`}</Typography>
          </Grid>
          <Grid item>
            <TextMarginLeft variant="caption">{`* ${localTimeSaved} by local cache`}</TextMarginLeft>
          </Grid>
          <Grid item>
            <TextMarginLeft variant="caption">{`* ${remoteTimeSaved} by Toolchain cache`}</TextMarginLeft>
          </Grid>
        </Grid>
      </Grid>
    </Grid>
  );

  return (
    <Tooltip title={timeSavedTooltip} arrow>
      {children}
    </Tooltip>
  );
};

const HitRateTooltip = ({ hitRate, hitRateLocal, hitRateRemote, children }: HitRateTooltipProps) => {
  const timeSavedTooltip = (
    <Grid container spacing={2}>
      <Grid item>
        <Grid container spacing={1}>
          <Grid item>
            <InvertedPolygon>
              <PolygonDnsDarkIcon color="primary" />
            </InvertedPolygon>
          </Grid>
          <Grid item>
            <LightTypography variant="subtitle2" color="primary">
              {`${hitRate} cache hit rate`}
            </LightTypography>
          </Grid>
        </Grid>
      </Grid>
      <Grid item>
        <Grid container>
          <Grid item xs={12}>
            <Typography variant="caption">{`${hitRate} of processes in this build were served from cache`}</Typography>
          </Grid>
          <Grid item xs={12}>
            <TextMarginLeft variant="caption">{`* ${hitRateLocal} hit rate for local cache`}</TextMarginLeft>
          </Grid>
          <Grid item xs={12}>
            <TextMarginLeft variant="caption">{`* ${hitRateRemote} hit rate for Toolchain cache`}</TextMarginLeft>
          </Grid>
        </Grid>
      </Grid>
    </Grid>
  );

  return (
    <Tooltip title={timeSavedTooltip} arrow>
      {children}
    </Tooltip>
  );
};

const Indicators = ({ indicators, displayTimeSaved = true }: IndicatorsProps) => {
  const {
    hit_fraction: hitFraction,
    saved_cpu_time: timeSaved,
    saved_cpu_time_local: timeSavedLocal,
    saved_cpu_time_remote: timeSavedRemote,
    hit_fraction_local: hitFractionLocal,
    hit_fraction_remote: hitFractionRemote,
  } = indicators;
  const hitRate = hitFraction.toLocaleString('en', { style: 'percent' });
  const hitRateLocal = hitFractionLocal.toLocaleString('en', { style: 'percent' });
  const hitRateRemote = hitFractionRemote.toLocaleString('en', { style: 'percent' });
  const totalTimeSaved = getMillisecondsHumanized(timeSaved);
  const localTimeSaved = getMillisecondsHumanized(timeSavedLocal);
  const remoteTimeSaved = getMillisecondsHumanized(timeSavedRemote);

  return (
    <Grid container spacing={1} justifyContent="center" alignItems="center" wrap="nowrap">
      {displayTimeSaved && (
        <Grid item>
          <TimeSavedTooltip
            totalTimeSaved={totalTimeSaved}
            localTimeSaved={localTimeSaved}
            remoteTimeSaved={remoteTimeSaved}
          >
            <GridNoMargin container gap={1} justifyContent="center" alignItems="center" wrap="nowrap">
              <Grid item>
                <Polygon>
                  <PolygonTimelapseIcon color="primary" />
                </Polygon>
              </Grid>
              <Grid item>
                <CacheWrapper>
                  <CacheInfoText variant="caption">{`${totalTimeSaved} saved`}</CacheInfoText>
                </CacheWrapper>
              </Grid>
            </GridNoMargin>
          </TimeSavedTooltip>
        </Grid>
      )}
      <Grid item>
        <HitRateTooltip hitRate={hitRate} hitRateLocal={hitRateLocal} hitRateRemote={hitRateRemote}>
          <GridNoMargin container gap={1} justifyContent="center" alignItems="center" wrap="nowrap">
            <Grid item xs="auto">
              <Polygon>
                <PolygonDnsIcon color="primary" />
              </Polygon>
            </Grid>
            <Grid item xs="auto">
              <CacheWrapper>
                <CacheInfoText variant="caption">{`${hitRate} from cache`}</CacheInfoText>
              </CacheWrapper>
            </Grid>
          </GridNoMargin>
        </HitRateTooltip>
      </Grid>
    </Grid>
  );
};

const NoIndicators = ({ loading }: NoIndicatorsProps) => {
  return (
    <Grid container spacing={1} justifyContent="center" alignItems="center" wrap="nowrap">
      <Grid item>
        <Tooltip
          title={
            <Typography variant="caption">
              The caching data is not <br />
              available at the moment.
            </Typography>
          }
          arrow
        >
          <GridNoMargin container gap={1} justifyContent="center" alignItems="center" wrap="nowrap">
            <Grid item xs="auto">
              <GreyPolygon>
                <PolygonDnsGreyIcon />
              </GreyPolygon>
            </Grid>
            <Grid item xs="auto">
              <CacheWrapperGrey>
                <ColorMediumGray variant="caption">
                  {!loading ? 'Data not available' : 'Data loading...'}
                </ColorMediumGray>
              </CacheWrapperGrey>
            </Grid>
          </GridNoMargin>
        </Tooltip>
      </Grid>
    </Grid>
  );
};

const CacheIndicators = ({ indicators, displayTimeSaved, loading }: CacheIndicatorsProps) =>
  indicators ? (
    <Indicators indicators={indicators} displayTimeSaved={displayTimeSaved} />
  ) : (
    <NoIndicators loading={loading} />
  );

export default CacheIndicators;
