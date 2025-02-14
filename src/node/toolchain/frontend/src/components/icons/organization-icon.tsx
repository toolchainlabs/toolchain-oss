/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import Avatar from '@mui/material/Avatar';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import { styled } from '@mui/material/styles';

type OrganizationIconProps = {
  slug: string;
  url: string;
  size: 'small' | 'extraSmall' | 'large';
};
type StyledAvatarProps = {
  size: { height: number; width: number };
};

const AVATAR_SIZES = {
  small: { height: 64, width: 64 },
  large: { height: 120, width: 120 },
  extraSmall: { height: 40, width: 40 },
};

const AvatarSmallAltText = styled(Typography)(({ theme }) => ({
  color: theme.palette.primary.dark,
  textTransform: 'uppercase',
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  width: '100%',
  height: '100%',
  backgroundColor: theme.palette.grey[50],
}));

const StyledAvatar = styled(Avatar, { shouldForwardProp: prop => prop !== 'size' })<StyledAvatarProps>(
  ({ theme, size }) => ({
    borderRadius: theme.spacing(1),
    backgroundColor: theme.palette.grey[100],
    ...size,
  })
);

export const getFirstLettersFromSlug = (slug: string) => {
  const splittedSlug = slug.split(' ');
  const firstLetters = splittedSlug.map(el => el.substr(0, 1));
  return firstLetters.join('').toUpperCase();
};

const OrganizationIcon = ({ slug, url, size }: OrganizationIconProps) => (
  <Tooltip title={slug}>
    <StyledAvatar alt={slug} src={url} variant="rounded" size={AVATAR_SIZES[size]}>
      {size === 'large' ? (
        <AvatarSmallAltText variant="h2">{getFirstLettersFromSlug(slug)}</AvatarSmallAltText>
      ) : (
        <AvatarSmallAltText variant="h4">{getFirstLettersFromSlug(slug)}</AvatarSmallAltText>
      )}
    </StyledAvatar>
  </Tooltip>
);

export default OrganizationIcon;
