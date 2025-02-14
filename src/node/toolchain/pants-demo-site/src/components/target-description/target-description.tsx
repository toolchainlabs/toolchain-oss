/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { styled } from '@mui/material/styles';
import { useSelector } from 'react-redux';
import { GlobalState } from '../../store/types';
import BasicNodeInfo from './basic-target-info';
import DependeciesList from './dependencies-list';
import GlobalTypesMap from './global-types-map';
import TargetTypesMap from './target-types-map';

const TargetDescription = () => {
  const selectedNode: string | undefined =
    useSelector((state: GlobalState) => state.node.selectedNode) || '';

  const TargetDescriptionWrapper = styled('div')(() => ({
    overflowY: 'auto',
    padding: 24,
    backgroundColor: '#fff',
    borderRadius: 8,
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    [`&::-webkit-scrollbar`]: {
      display: 'none',
    },
  }));

  const StyledGradient = styled('div')(() => ({
    height: '40px',
    background:
      'linear-gradient(180deg, rgba(255, 255, 255, 0) 0%, #FFFFFF 100%)',
    width: 'calc(100% - 48px)',
    position: 'absolute',
    bottom: '0',
    pointerEvents: 'none',
  }));

  const SectionWrapper = styled('div')(() => ({
    marginBottom: 24,
  }));

  const isTargetSelected = !!selectedNode;

  return (
    <TargetDescriptionWrapper>
      {isTargetSelected && (
        <SectionWrapper>
          <BasicNodeInfo fullName={selectedNode} />
        </SectionWrapper>
      )}
      {isTargetSelected && (
        <SectionWrapper>
          <DependeciesList fullName={selectedNode} />
        </SectionWrapper>
      )}
      {!isTargetSelected && <GlobalTypesMap />}
      {isTargetSelected && <TargetTypesMap fullName={selectedNode} />}
      <StyledGradient />
    </TargetDescriptionWrapper>
  );
};

export default TargetDescription;
