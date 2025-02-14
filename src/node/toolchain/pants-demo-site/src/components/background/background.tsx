/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { styled } from '@mui/material/styles';

type BackgroundProps = { children: React.ReactNode };

const HeaderContent = styled('div')(({ theme }) => ({
  minHeight: '100vh',
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'space-between',
  background: 'linear-gradient(180deg, #FFFFFF 0%, #F5F5F5 100%)',
  [theme.breakpoints.down('md')]: {
    background: '#fff',
  },
}));

const BackgroundWrapper = styled('div')(() => ({
  zIndex: 4,
  position: 'absolute',
  top: 0,
  left: 0,
  width: '100%',
  height: '100%',
  maxHeight: 850,
  overflow: 'hidden',
  pointerEvents: 'none',
}));

const Triangle = styled('div')(({ theme }) => ({
  width: 0,
  height: 0,
  borderStyle: 'solid',
  borderWidth: '270px 700px 0 0',
  borderColor: '#212B40 transparent transparent transparent',
  transition: 'border-width 0.15s',
  [theme.breakpoints.down('lg')]: {
    borderWidth: '270px 500px 0 0',
  },
  [theme.breakpoints.down('md')]: {
    clipPath: ' polygon(0 0, 0% 100%, 100% 0)',
    backgroundColor: '#212B40',
    borderWidth: 0,
    width: '100%',
    height: 167,
  },
}));

const GradientContainer = styled('div')(() => ({
  position: 'absolute',
  top: 0,
  left: 0,
  width: '100%',
}));

const Gradient = styled('div')(({ theme }) => ({
  position: 'absolute',
  width: '100%',
  height: '84vh',
  zIndex: 2,
  top: 0,
  left: 0,
  right: 0,
  backgroundImage: `linear-gradient(
    108.43deg,
    rgba(145, 202, 255, 0.12) 0%,
    rgba(145, 202, 255, 0) 99.99%
  )`,
  backgroundAttachment: 'fixed',
  backgroundPosition: 'center',
  clipPath: 'polygon(100% 100%, 0 0, 100vw 0)',
  [theme.breakpoints.down('md')]: {
    height: 216,
  },
}));

const Background = ({ children }: BackgroundProps) => {
  return (
    <HeaderContent>
      <BackgroundWrapper>
        <Triangle />
        <GradientContainer>
          <Gradient />
        </GradientContainer>
      </BackgroundWrapper>
      {children}
    </HeaderContent>
  );
};

export default Background;
