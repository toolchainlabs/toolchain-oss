/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { useSelector, useDispatch } from 'react-redux';
import { styled } from '@mui/material/styles';
import IconButton from '@mui/material/IconButton';
import RefreshIcon from '@mui/icons-material/Refresh';
import AddIcon from '@mui/icons-material/Add';
import RemoveIcon from '@mui/icons-material/Remove';
import Grid from '@mui/material/Grid';
import VisibleGraph from '../models/visible-graph';
import { GlobalState } from '../store/types';
import { visibleGraphSet } from '../store/visibleGraphSlice';
import { nodeFocused, nodeSelected } from '../store/nodeSlice';
import { graphZoomDifferenceSet } from '../store/graphZoomSlice';
import { sep } from '../models/utils';
import OnGraphToolTip from './graph-grow';

const StyledButtonGridContainer = styled(Grid)(({ theme }) => ({
  position: 'absolute',
  top: 0,
  right: 0,
  margin: 0,
  width: '100%',
  paddingTop: theme.spacing(2),
  paddingLeft: theme.spacing(2),
  paddingRight: theme.spacing(2),
}));

const StyledButton = styled(IconButton)(({ theme }) => ({
  borderRadius: theme.spacing(0.5),
  padding: 5,
  backgroundColor: theme.palette.background.default,
  border: '1px solid transparent',
  boxShadow: 'none',
  [`&:hover`]: {
    borderColor: `rgba(4, 78, 243, 0.5)`,
    backgroundColor: theme.palette.background.default,
    boxShadow: 'none',
  },
  [`&:disabled`]: {
    backgroundColor: theme.palette.grey[100],
  },
}));
const StyledRefreshIcon = styled(RefreshIcon)(() => ({
  fontSize: 36,
}));
const StyledPlusIcon = styled(AddIcon)(() => ({
  fontSize: 36,
}));
const StyledMinusIcon = styled(RemoveIcon)(() => ({
  fontSize: 36,
}));

const OnGraphControls = () => {
  const hd = useSelector(
    (state: GlobalState) => state.hierarchicalDigraph.graph
  );

  const vg = useSelector((state: GlobalState) => state.visibleGraph.graph);

  const dispatch = useDispatch();

  const resetGraphHandler = () => {
    if (hd && isNotOnRootLevel) {
      const newVg = VisibleGraph.initial(hd);
      dispatch(visibleGraphSet(newVg));
      dispatch(nodeSelected(''));
      dispatch(nodeFocused(''));
    }
  };

  const zoomIn = () => {
    const zoomDiff = 0.3;
    dispatch(graphZoomDifferenceSet(zoomDiff));
  };

  const zoomOut = () => {
    const zoomDiff = -0.3;
    dispatch(graphZoomDifferenceSet(zoomDiff));
  };

  const visibleNodes = vg?.visibleNodes || new Set<string>();
  let isNotOnRootLevel = false;
  for (const addr of visibleNodes) {
    if (addr.search(sep) >= 0) {
      isNotOnRootLevel = true;
      break;
    }
  }

  const isRefreshDisabled = !isNotOnRootLevel;

  return (
    <StyledButtonGridContainer
      container
      spacing={1}
      justifyContent="space-between"
    >
      <Grid item>
        <OnGraphToolTip />
      </Grid>
      <Grid item>
        <Grid container spacing={1}>
          <Grid item>
            <StyledButton onClick={zoomOut}>
              <StyledMinusIcon color="primary" />
            </StyledButton>
          </Grid>
          <Grid item>
            <StyledButton onClick={zoomIn}>
              <StyledPlusIcon color="primary" />
            </StyledButton>
          </Grid>
          <Grid item>
            <StyledButton
              onClick={resetGraphHandler}
              id="refresh-graph"
              disabled={isRefreshDisabled}
            >
              <StyledRefreshIcon
                color={isRefreshDisabled ? 'disabled' : 'primary'}
              />
            </StyledButton>
          </Grid>
        </Grid>
      </Grid>
    </StyledButtonGridContainer>
  );
};

export default OnGraphControls;
