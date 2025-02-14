/*
Copyright 2019 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import Collapse from '@mui/material/Collapse';
import ExpandMore from '@mui/icons-material/ExpandMore';
import ExpandLess from '@mui/icons-material/ExpandLess';
import Button from '@mui/material/Button';
import Paper from '@mui/material/Paper';

import { dateTimeAndTimeFromNowLocal, durationToFormat } from 'utils/datetime-formats';
import { Build, Platform } from 'common/interfaces/builds';
import CodeBlock from 'components/codeblock/codeblock';
import RunType from 'common/enums/RunType';
import ExternalLinkChip from 'components/chips/external-link-chip/external-link-chip';
import TextChip from 'components/chips/text-chip/text-chip';
import AvatarChip from 'components/chips/avatar-chip/avatar-chip';
import paths from 'utils/paths';
import { styled } from '@mui/material/styles';

const LabelText = styled(Typography)(({ theme }) => ({
  color: theme.palette.text.disabled,
  paddingBottom: theme.spacing(1),
}));

const RepoLink = styled(Link)(({ theme }) => ({
  color: theme.palette.primary.main,
}));

const ShowMoreInfoText = styled(Typography)(() => ({
  fontSize: 12,
  letterSpacing: 1,
  marginLeft: 12.5,
}));

const ShowMoreInfoButton = styled(Button)(() => ({
  padding: 6,
}));

const StyledCollapse = styled(Collapse)(({ theme }) => ({
  width: '100%',
  paddingLeft: theme.spacing(3),
  paddingTop: theme.spacing(3),
}));

const StyledPaper = styled(Paper)(({ theme }) => ({
  padding: theme.spacing(3),
  border: `1px solid transparent`,
  borderRadius: 10,
}));

const CiContextContainer = styled(Grid)(({ theme }) => ({
  marginTop: theme.spacing(0.5),
}));

type DetailsProps = {
  data: Build;
};

const Details = ({ data }: DetailsProps) => {
  const { orgSlug } = useParams();
  const [showMore, setShowMore] = useState<boolean>(false);

  const showMoreIcon = showMore ? <ExpandLess /> : <ExpandMore />;
  const showMoreText = `SHOW ${showMore ? 'LESS' : 'MORE'} INFO`;

  const getPlatformText = ({
    python_implementation: pythonImplementation,
    python_version: pythonVersion,
    architecture,
    os,
    os_release: osRelease,
    cpu_count: cpuCount,
    mem_bytes: memBytes,
  }: Platform) => {
    const memGigabyte = (memBytes / (1024 * 1024 * 1024)).toFixed(0);
    return (
      <div>
        {`${pythonImplementation} ${pythonVersion} on ${architecture} ${os} ${osRelease}`}
        <br />
        {`(${cpuCount} cores, ${memGigabyte}GB RAM)`}
      </div>
    );
  };

  const LabelValue = ({ label, value }: { label: string; value: React.ReactNode }) => (
    <div>
      <div>
        <LabelText variant="overline">{label}</LabelText>
      </div>
      <div>{value}</div>
    </div>
  );

  const GeneralDetails = () => {
    return (
      <Grid item xs={12}>
        <Grid container spacing={5}>
          <Grid item>
            <LabelValue
              label="STARTED"
              value={<Typography variant="body1">{dateTimeAndTimeFromNowLocal(data.datetime)}</Typography>}
            />
          </Grid>
          <Grid item>
            <LabelValue
              label="DURATION"
              value={
                <Typography variant="body1">{data.run_time ? durationToFormat(data.run_time) : 'Unknown'}</Typography>
              }
            />
          </Grid>
          <Grid item>
            <LabelValue
              label="GOALS"
              value={data.goals.map(goal => (
                <TextChip key={goal} text={goal} />
              ))}
            />
          </Grid>
          <Grid item>
            <LabelValue
              label="REPOSITORY"
              value={
                <RepoLink to={paths.builds(orgSlug, data.repo_slug)}>
                  <Typography variant="body1">{data.repo_slug}</Typography>
                </RepoLink>
              }
            />
          </Grid>
          <Grid item>
            <LabelValue
              label="USER"
              value={
                <Link to={`${paths.builds(orgSlug, data.repo_slug)}?user=${data.user.username}`}>
                  <AvatarChip text={data.user.full_name} avatar={data.user.avatar_url} />
                </Link>
              }
            />
          </Grid>
          <Grid item>
            <LabelValue
              label="PLATFORM"
              value={
                <Typography component="div" variant="body1">
                  {!!data.platform ? getPlatformText(data.platform) : 'Not available'}
                </Typography>
              }
            />
          </Grid>
        </Grid>
      </Grid>
    );
  };

  const EnviormentDetails = () => {
    const title = data.is_ci ? 'CI info' : 'Local machine info';
    const runType =
      data.ci_info?.run_type && data.ci_info.run_type === RunType.PULL_REQUEST ? 'Pull Request' : 'Branch';
    const branch = data.branch || 'No branch reported';
    const prNumber = data.ci_info?.pull_request;
    const prTitle = data.title;

    return (
      <Grid item xs={12}>
        <StyledPaper elevation={0}>
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <Typography variant="h4">{title}</Typography>
            </Grid>
            <Grid item xs={12}>
              {data.is_ci ? (
                <Grid container spacing={2}>
                  <Grid item xs={12} position="relative">
                    <LabelValue
                      label="CONTEXT"
                      value={
                        <CiContextContainer container spacing={1} alignItems="center">
                          {!!prTitle && (
                            <Grid item>
                              {prNumber ? (
                                <RepoLink to={`${paths.builds(orgSlug, data.repo_slug)}?pr=${prNumber}`}>
                                  {prTitle}
                                </RepoLink>
                              ) : (
                                <Typography variant="body1" color="text.primary">
                                  {prTitle}
                                </Typography>
                              )}
                            </Grid>
                          )}
                          {data.ci_info.links?.length &&
                            data.ci_info.links.map(({ icon, text, link }) => (
                              <Grid item key={link}>
                                <ExternalLinkChip text={text} link={link} icon={icon} />
                              </Grid>
                            ))}
                        </CiContextContainer>
                      }
                    />
                  </Grid>
                  <Grid item xs={12}>
                    <Grid container spacing={5}>
                      <Grid item>
                        <LabelValue label="BRANCH" value={<Typography variant="body1">{data.branch}</Typography>} />
                      </Grid>
                      <Grid item>
                        <LabelValue label="RUN TYPE" value={<Typography variant="body1">{runType}</Typography>} />
                      </Grid>
                      <Grid item>
                        <LabelValue
                          label="JOB"
                          value={<Typography variant="body1">{data.ci_info.job_name}</Typography>}
                        />
                      </Grid>
                      <Grid item>
                        <LabelValue
                          label="BUILD NUMBER"
                          value={<Typography variant="body1">{data.ci_info.build_num}</Typography>}
                        />
                      </Grid>
                    </Grid>
                  </Grid>
                </Grid>
              ) : (
                <Grid container spacing={5}>
                  <Grid item>
                    <LabelValue label="MACHINE" value={<Typography variant="body1">{data.machine}</Typography>} />
                  </Grid>
                  <Grid item>
                    <LabelValue label="BRANCH" value={<Typography variant="body1">{branch}</Typography>} />
                  </Grid>
                </Grid>
              )}
            </Grid>
          </Grid>
        </StyledPaper>
      </Grid>
    );
  };

  return (
    <Grid container spacing={3} onClick={e => e.stopPropagation()}>
      <Grid item xs={12}>
        <Typography variant="h3">Command</Typography>
      </Grid>
      <Grid item xs={12}>
        <CodeBlock>{data.cmd_line}</CodeBlock>
      </Grid>
      <StyledCollapse in={showMore} timeout="auto" unmountOnExit>
        <Grid container spacing={3}>
          <GeneralDetails />
          <EnviormentDetails />
        </Grid>
      </StyledCollapse>
      <Grid item xs={12}>
        <ShowMoreInfoButton variant="text" color="primary" onClick={() => setShowMore(!showMore)}>
          {showMoreIcon}
          <ShowMoreInfoText variant="h3">{showMoreText}</ShowMoreInfoText>
        </ShowMoreInfoButton>
      </Grid>
    </Grid>
  );
};

export default Details;
