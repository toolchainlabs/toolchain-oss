/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import TypeIndicator from '../type-indicator';
import { getNodeColor } from '../../paint-node-utils';
import { TypesMap } from '../../store/types';

type DisplayTypesMapType = {
  types?: TypesMap;
  label: string;
};

const DisplayTypesMap = ({ types, label }: DisplayTypesMapType) => {
  const NUM_OF_HIGHLIGHTED_TYPES = 5;

  const sortedTypes = !types
    ? []
    : Array.from(types.keys())
        .map(el => ({
          key: el,
          value: types.get(el) || 0,
        }))
        .sort((el1, el2) => {
          return el2.value - el1.value;
        });

  const mostCommonTypes = sortedTypes.slice(0, NUM_OF_HIGHLIGHTED_TYPES);
  const restOfTypes = sortedTypes.slice(NUM_OF_HIGHLIGHTED_TYPES);

  const numOfRestTypes = restOfTypes.reduce(
    (prev, curr) => prev + curr.value,
    0
  );

  const otherTargetTypesColor = '#D1D1D1';

  return (
    <Grid container flexDirection="column" spacing={2}>
      <Grid item>
        <Typography variant="h3">{label}</Typography>
      </Grid>
      <Grid item>
        <Grid container flexDirection="column" spacing={1}>
          <Grid item>
            <Grid container justifyContent="space-between">
              <Grid item>
                <Typography variant="overline" color="textSecondary">
                  Target type
                </Typography>
              </Grid>
              <Grid item>
                <Typography variant="overline" color="textSecondary">
                  count
                </Typography>
              </Grid>
            </Grid>
          </Grid>
          <Grid item>
            <Grid container flexDirection="column" spacing={1}>
              {mostCommonTypes.map(el => (
                <Grid item key={el.key}>
                  <Grid container justifyContent="space-between">
                    <Grid item>
                      <Grid container spacing={0.5} alignItems="center">
                        <Grid item>
                          <TypeIndicator color={getNodeColor(el.key)} />
                        </Grid>
                        <Grid item>
                          <Typography variant="body1">{el.key}</Typography>
                        </Grid>
                      </Grid>
                    </Grid>
                    <Grid item>
                      <Typography variant="subtitle1">{el.value}</Typography>
                    </Grid>
                  </Grid>
                </Grid>
              ))}
              <Grid item>
                <Grid container justifyContent="space-between">
                  <Grid item>
                    <Grid container spacing={0.5} alignItems="center">
                      <Grid item>
                        <TypeIndicator color={otherTargetTypesColor} />
                      </Grid>
                      <Grid item>
                        <Typography variant="body1">
                          Other target types
                        </Typography>
                      </Grid>
                    </Grid>
                  </Grid>
                  <Grid item>
                    <Typography variant="subtitle1">
                      {numOfRestTypes}
                    </Typography>
                  </Grid>
                </Grid>
              </Grid>
            </Grid>
          </Grid>
        </Grid>
      </Grid>
    </Grid>
  );
};

export default DisplayTypesMap;
