/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { useEffect, useRef } from 'react';
import { styled } from '@mui/material/styles';
import { useSelector, useDispatch } from 'react-redux';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import Grid from '@mui/material/Grid/Grid';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';

import { GlobalState, NodeAdress } from '../../store/types';
import { sep } from '../../models/utils';
import { nodeSelected, nodeFocused, nodeHovered } from '../../store/nodeSlice';
import {
  visibleGraphExpanded,
  visibleGraphCollapsed,
} from '../../store/visibleGraphSlice';

type FileSystemUnitType = {
  fullName: string;
};

const StyledChevronRightIcon = styled(ChevronRightIcon)(() => ({
  color: 'rgba(0, 0, 0, 0.38)',
  fontSize: 20,
}));
const StyledExpandMoreIcon = styled(ExpandMoreIcon)(() => ({
  color: 'rgba(0, 0, 0, 0.38)',
  fontSize: 20,
}));
const StyledBorderSeparator = styled('div')(
  ({ haschildren }: { haschildren: number }) => ({
    width: 5.5,
    borderTop: `1px solid rgba(0, 0, 0, 0.38)`,
    marginTop: 11,
    marginRight: 8,
    paddingBottom: 8,
    marginLeft: haschildren ? '-33.5px' : '-13.5px',
  })
);
const StyledIconButton = styled(IconButton)(() => ({
  padding: 0,
  position: 'relative',
  top: '-2px',
}));
const StyledDisplayName = styled(Typography)(({ theme }) => ({
  wordBreak: 'break-word',
  [`&:hover`]: {
    color: theme.palette.primary.light,
  },
}));
const ChildrenContainer = styled('div')(
  ({ fullname }: { fullname: string }) => ({
    marginLeft: fullname ? 9.5 : 0,
    paddingLeft: fullname ? 13.5 : 0,
    borderLeft: `${fullname ? 1 : 0}px solid rgba(0, 0, 0, 0.38)`,
    position: 'relative',
    marginTop: 5.5,
  })
);

export default function FileSystemUnit({ fullName }: FileSystemUnitType) {
  const dispatch = useDispatch();

  const vg = useSelector((state: GlobalState) => state.visibleGraph.graph);

  const selectedNode: NodeAdress = useSelector(
    (state: GlobalState) => state.node.selectedNode
  );

  const focusedNode: NodeAdress = useSelector(
    (state: GlobalState) => state.node.focusedNode
  );

  const hoveredNode: NodeAdress = useSelector(
    (state: GlobalState) => state.node.hoveredNode
  );

  const fileSystemUnitRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (fullName === focusedNode) {
      fileSystemUnitRef.current?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }
  }, [focusedNode]);

  const hd = vg?.hierarchicalDigraph;

  const myChildrenNodes: Set<string> =
    hd?.findChildren(fullName) || new Set<string>();
  const hasChildren = myChildrenNodes.size > 0;

  const isVisibleInGraph = vg?.isVisible(fullName);
  const isVisibleInFS = isVisibleInGraph || vg?.hasVisibleDescendant(fullName);
  const isOpened = hasChildren && !isVisibleInGraph;
  const isSelectedNode = fullName === selectedNode;
  const isHoveredNode = fullName === hoveredNode;

  const isColored = isSelectedNode || isHoveredNode;

  const splitedName = fullName.split(sep);
  const levelOfNesting = splitedName.length;
  const displayName = splitedName[levelOfNesting - 1];

  const childrenArray = Array.from(myChildrenNodes);

  const toggleElement = () => {
    if (isVisibleInGraph && hasChildren) {
      dispatch(visibleGraphExpanded(fullName));
      dispatch(nodeFocused(fullName));
    } else if (!isVisibleInGraph && hasChildren) {
      dispatch(visibleGraphCollapsed(fullName));
      dispatch(nodeFocused(fullName));
      const selectedNodeString = selectedNode || '';
      const isCurrentNodeSelected = fullName === selectedNodeString;
      const isChildSelected =
        !isCurrentNodeSelected && selectedNodeString.search(fullName) >= 0;
      if (isChildSelected) {
        dispatch(nodeSelected(''));
      }
    }
  };

  const selectElement = () => {
    dispatch(nodeSelected(fullName));
    dispatch(nodeFocused(fullName));
  };

  const onHoverHandler = () => dispatch(nodeHovered(fullName));
  const onLeaveHandler = () => dispatch(nodeHovered(''));

  const chevronIcon = isOpened ? (
    <StyledExpandMoreIcon />
  ) : (
    <StyledChevronRightIcon />
  );

  return (
    <>
      {!!fullName && isVisibleInFS ? (
        <Grid
          container
          ref={fileSystemUnitRef}
          ml={fullName ? '13.5' : '0'}
          alignItems="center"
          minHeight={20}
          onMouseEnter={onHoverHandler}
          onMouseLeave={onLeaveHandler}
          maxWidth={300}
        >
          {hasChildren && (
            <Grid item minHeight={20}>
              <StyledIconButton
                onClick={toggleElement}
                id={`chevron-${fullName}`}
              >
                {chevronIcon}
              </StyledIconButton>
            </Grid>
          )}
          {levelOfNesting > 1 ? (
            <Grid item>
              <Grid container>
                <Grid item>
                  <StyledBorderSeparator haschildren={hasChildren ? 1 : 0} />
                </Grid>
              </Grid>
            </Grid>
          ) : null}
          <Grid item xs minHeight={20}>
            <StyledDisplayName
              variant="body2"
              color={isColored ? 'primary' : 'text'}
              sx={{ cursor: 'pointer' }}
              onClick={selectElement}
            >
              {displayName}
            </StyledDisplayName>
          </Grid>
        </Grid>
      ) : null}
      {hasChildren && !isVisibleInGraph && (
        <ChildrenContainer fullname={fullName}>
          {childrenArray.map(addr => (
            <FileSystemUnit key={addr} fullName={addr} />
          ))}
        </ChildrenContainer>
      )}
    </>
  );
}
