/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { styled } from '@mui/material/styles';
import { useSelector } from 'react-redux';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import { sep } from '../../models/utils';
import { GlobalState } from '../../store/types';
import { getNodeColor, ROLLUP_COLOR } from '../../paint-node-utils';
import { LeafNode } from '../../models/Node';

type DependeciesListType = {
  fullName: string;
};

const DependeciesList = ({ fullName }: DependeciesListType) => {
  const hd = useSelector(
    (state: GlobalState) => state.hierarchicalDigraph.graph
  );

  const depListNames = hd?.getNodeEdges(fullName).filter(el => el !== fullName);

  const hasDependencies = !!depListNames?.length;

  const DependecyChip = ({ elName }: { elName: string }) => {
    const buttonData = hd?.allRolledUpNodes.get(elName);

    const isRollup = !buttonData?.isLeaf();

    const backgroundColor = isRollup
      ? ROLLUP_COLOR
      : getNodeColor((buttonData as LeafNode).nodeType || '');

    const splittedName = elName.split(sep);
    const numOfElements = splittedName.length;

    const displayName = splittedName[numOfElements - 1];

    const StyledChip = styled('button')(({ theme }) => ({
      padding: '0 10px',
      border: '1px solid rgba(0, 0, 0, 0.8)',
      borderRadius: isRollup ? 4 : 20,
      backgroundColor: backgroundColor,
      color: theme.palette.text.primary,
      marginRight: 8,
      marginBottom: 8,
    }));

    return (
      <StyledChip>
        <Typography variant="body1">{displayName}</Typography>
      </StyledChip>
    );
  };

  return (
    <Grid container spacing={1} flexDirection="column">
      <Grid item>
        <Typography variant="subtitle1">Dependencies</Typography>
      </Grid>
      <Grid item>
        {hasDependencies ? (
          <Grid container flexWrap="wrap">
            {depListNames?.map(el => (
              <Grid item key={el}>
                <DependecyChip elName={el} />
              </Grid>
            ))}
          </Grid>
        ) : (
          <Typography variant="body1" color="textSecondary">
            This target has no dependencies.
          </Typography>
        )}
      </Grid>
    </Grid>
  );
};

export default DependeciesList;
