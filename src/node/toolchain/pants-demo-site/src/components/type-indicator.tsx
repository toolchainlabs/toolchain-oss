/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { styled } from '@mui/material/styles';

type TypeIndicatorType = {
  color: string;
  isRounded?: boolean;
  size?: number;
};

const TypeIndicator = ({
  color,
  isRounded = true,
  size = 18,
}: TypeIndicatorType) => {
  const StyledIndicator = styled('div')(() => ({
    height: size,
    width: size,
    borderRadius: isRounded ? 20 : 4,
    backgroundColor: color,
    border: '1px solid rgba(0, 0, 0, 0.8)',
  }));

  return <StyledIndicator />;
};

export default TypeIndicator;
