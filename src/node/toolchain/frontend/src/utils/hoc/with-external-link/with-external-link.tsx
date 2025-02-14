/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import Avatar from '@mui/material/Avatar';
import { styled } from '@mui/material/styles';

import {
  CircleCiIcon,
  ExternalLinkIcon,
  GithubIcon,
  TravisCiIcon,
  BitBucketIcon,
  BuildkiteIcon,
  JenkinsIcon,
} from 'assets/icons';

type MapExternalIcon = { [key: string]: JSX.Element };

const MAP_EXTERNAL_ICON: MapExternalIcon = {
  github: <Avatar alt="GitHub link icon" src={GithubIcon} />,
  circleci: <Avatar alt="Circle ci link icon" src={CircleCiIcon} />,
  'travis-ci': <Avatar alt="Travis CI link icon" src={TravisCiIcon} />,
  bitbucket: <Avatar alt="Bitbucket link icon" src={BitBucketIcon} />,
  buildkite: <Avatar alt="Buildkite link icon" src={BuildkiteIcon} />,
  jenkins: <Avatar alt="Jenkins link icon" src={JenkinsIcon} />,
};

const StyledAvatar = styled(Avatar)(() => ({
  borderRadius: 0,
  [`& img`]: {
    width: 13,
    height: 13,
  },
}));

const withExternalLink =
  <P extends object>(Component: React.ComponentType<P>, url: string, icon: string): React.FC<P> =>
  (props: P) => {
    const i = MAP_EXTERNAL_ICON[icon] || <StyledAvatar alt="External link icon" src={ExternalLinkIcon} />;

    return (
      <a type="external" href={url} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()}>
        {/* eslint-disable-next-line react/jsx-props-no-spreading */}
        <Component Icon={i} {...props} />
      </a>
    );
  };

export default withExternalLink;
