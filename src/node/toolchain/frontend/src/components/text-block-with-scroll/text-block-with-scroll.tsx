/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useRef, useState, useEffect } from 'react';
import Box from '@mui/material/Box';
import { styled } from '@mui/material/styles';
import Ansi from 'ansi-to-react';

type TextBlockWithScrollProps = {
  children: JSX.Element | string;
  size: 'small' | 'large';
  color: Color;
};

type Color = 'blue' | 'gray';

type StyledGradientBoxProps = {
  gradientColor?: Color;
};

type StyledTextBoxProps = Pick<TextBlockWithScrollProps, 'size'> & { boxColor: Color };

const GRADIENT_COLORS = {
  blue: 'linear-gradient(180deg, rgba(235, 249, 250, 0) 0%, #EBF9FA 100%)',
  gray: 'linear-gradient(180deg, rgba(245, 245, 245, 0) 0%, #F5F5F5 100%)',
};

const BLOCK_SIZE = {
  small: 200,
  large: 400,
};

const StyledGradientBox = styled(Box, { shouldForwardProp: prop => prop !== 'gradientColor' })<StyledGradientBoxProps>(
  ({ theme, gradientColor }) => {
    const background = { background: GRADIENT_COLORS[gradientColor] };

    return {
      position: 'absolute',
      width: '100%',
      height: 40,
      bottom: 0,
      borderBottomRightRadius: theme.spacing(1),
      borderBottomLeftRadius: theme.spacing(1),
      ...background,
    };
  }
);

const StyledTextBox = styled(Box, {
  shouldForwardProp: prop => !(['boxColor', 'size'] as PropertyKey[]).includes(prop),
})<StyledTextBoxProps>(({ theme, boxColor, size }) => {
  const backgroundColor = { backgroundColor: boxColor !== 'blue' ? theme.palette.grey[50] : 'rgba(0, 169, 183, 0.08)' };
  const maxHeight = { maxHeight: BLOCK_SIZE[size] };

  return {
    margin: 0,
    padding: theme.spacing(3),
    border: '1px solid transparent',
    borderRadius: theme.spacing(1),
    whiteSpace: 'pre-wrap',
    overflow: 'hidden',
    overflowY: 'scroll',
    ...maxHeight,
    ...backgroundColor,
    [`& code`]: {
      fontFamily: 'Fira Code, sans-serif',
      fontStyle: 'normal',
      fontSize: 14,
      fontWeight: 400,
      wordBreak: 'break-all',
    },
  };
});

const TextBlockWithScroll = ({ children, size, color }: TextBlockWithScrollProps) => {
  const [height, setHeight] = useState(0);
  const ref = useRef(null);

  useEffect(() => {
    setHeight(ref.current.clientHeight);
  }, []);

  const showGradient = height === BLOCK_SIZE[size];

  const isContentString = typeof children === 'string';

  const content = isContentString ? <Ansi>{children as string}</Ansi> : children;

  return (
    <Box position="relative">
      <div ref={ref}>
        <StyledTextBox boxColor={color} size={size}>
          {content}
        </StyledTextBox>
      </div>
      {showGradient && <StyledGradientBox gradientColor={color} />}
    </Box>
  );
};

export default TextBlockWithScroll;
