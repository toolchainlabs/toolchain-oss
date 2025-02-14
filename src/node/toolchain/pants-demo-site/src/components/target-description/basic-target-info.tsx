/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { styled } from '@mui/material/styles';
import { useSelector, useDispatch } from 'react-redux';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';

import { visibleGraphExpanded } from '../../store/visibleGraphSlice';
import { sep } from '../../models/utils';
import { GlobalState } from '../../store/types';
import { LeafNode } from '../../models/Node';
import { getNodeColor, ROLLUP_COLOR } from '../../paint-node-utils';
import TypeIndicator from '../type-indicator';

type BasicTargetInfoType = {
  fullName: string;
};

const ExpandButton = styled(Button)(({ theme }) => ({
  backgroundColor: theme.palette.primary.main,
  color: '#fff',
  border: 0,
  borderRadius: 4,
  padding: '4px 12px',
  cursor: 'pointer',
}));

const BasicTargetInfo = ({ fullName }: BasicTargetInfoType) => {
  const dispatch = useDispatch();

  const hd = useSelector(
    (state: GlobalState) => state.hierarchicalDigraph.graph
  );

  const vg = useSelector((state: GlobalState) => state.visibleGraph.graph);

  const selectedTargetData = hd?.allRolledUpNodes.get(fullName);

  const isDisplayed = vg?.isVisible(fullName) || false;
  const isRollup = !selectedTargetData?.isLeaf();

  const isExpandable = isDisplayed && isRollup;

  const nodeType = isRollup
    ? 'Expandable'
    : (selectedTargetData as LeafNode).nodeType || '';

  const indicatorColor = isRollup ? ROLLUP_COLOR : getNodeColor(nodeType);

  const splittedName = fullName.split(sep);
  const numOfElements = splittedName.length;

  const displayName = splittedName[numOfElements - 1];

  const onExpand = () => {
    dispatch(visibleGraphExpanded(fullName));
  };

  return (
    <Grid container spacing={2} flexDirection="column">
      <Grid item>
        <Grid container justifyContent="space-between">
          <Grid item>
            <Typography variant="h3" id="description-display-name">
              {displayName}
            </Typography>
          </Grid>
          {isExpandable && (
            <Grid item>
              <ExpandButton variant="contained" onClick={onExpand}>
                <Typography variant="button">expand</Typography>
              </ExpandButton>
            </Grid>
          )}
        </Grid>
      </Grid>
      <Grid item>
        <Grid container spacing={3}>
          <Grid item>
            <Typography variant="subtitle1">Type</Typography>
          </Grid>
          <Grid item>
            <Grid container spacing={0.5} alignItems="center">
              <Grid item>
                <TypeIndicator color={indicatorColor} isRounded={!isRollup} />
              </Grid>
              <Grid item>
                <Typography variant="body1">{nodeType}</Typography>
              </Grid>
            </Grid>
          </Grid>
        </Grid>
      </Grid>
    </Grid>
  );
};

export default BasicTargetInfo;
