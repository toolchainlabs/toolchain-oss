/*
Copyright 2019 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import Avatar from '@mui/material/Avatar';
import { styled } from '@mui/material/styles';

type UserAvatarProps = {
  url: string | null;
  size?: 'small' | 'large' | 'extraSmall';
  userFullName: string;
};

const StyledAvatar = styled(Avatar)(({ theme }) => ({
  border: 0,
  borderRadius: theme.spacing(1),
  margin: '0 auto',
}));

const UserAvatar = ({ url, size = 'small', userFullName }: UserAvatarProps) => {
  const sizes = {
    small: {
      width: 64,
      height: 64,
    },
    extraSmall: {
      width: 40,
      height: 40,
    },
    large: {
      width: 120,
      height: 120,
    },
  };

  const sizeValues = sizes[size];

  const avatarUrl = url || '/';

  return <StyledAvatar alt={userFullName} src={avatarUrl} variant="rounded" sx={{ ...sizeValues }} />;
};

export default UserAvatar;
