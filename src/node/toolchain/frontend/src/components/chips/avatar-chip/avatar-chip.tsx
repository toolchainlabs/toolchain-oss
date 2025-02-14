/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import Avatar from '@mui/material/Avatar';
import { styled } from '@mui/material/styles';

interface AvatarChipProps {
  text: string;
  avatar: string | null;
  size?: 'small' | 'medium';
  variant?: 'filled' | 'outlined';
}

const StyledChip = styled(Chip)(() => ({ cursor: 'pointer', backgroundColor: 'transparent' }));
const StyledAvatarPlaceHolder = styled('div')(({ theme }) => ({
  width: 24,
  height: 24,
  backgroundColor: 'rgba(0, 169, 183, 0.08)',
  color: theme.palette.primary.dark,
  borderRadius: 20,
}));

const SmallLabel = styled(Typography)(() => ({ fontSize: 12 }));

const AvatarChip = ({ text, size = 'small', variant = 'outlined', avatar }: AvatarChipProps) => {
  const UserAvatar = avatar ? (
    <Avatar alt={text} src={avatar} />
  ) : (
    <Avatar
      alt={text}
      component={() => (
        <StyledAvatarPlaceHolder>
          <Typography variant="h4" align="center">
            {text.charAt(0).toUpperCase()}
          </Typography>
        </StyledAvatarPlaceHolder>
      )}
    />
  );

  return (
    <StyledChip
      variant={variant}
      size={size}
      avatar={UserAvatar}
      label={
        size === 'small' ? (
          <SmallLabel variant="body2">{text}</SmallLabel>
        ) : (
          <Typography variant="body2">{text}</Typography>
        )
      }
    />
  );
};

export default AvatarChip;
