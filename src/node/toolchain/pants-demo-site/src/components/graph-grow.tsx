/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { useState } from 'react';
import Typography from '@mui/material/Typography';
import Grid from '@mui/material/Grid';
import IconButton from '@mui/material/IconButton';
import { styled } from '@mui/material/styles';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { NodeColors, getNodeColor } from '../paint-node-utils';
import Grow from '@mui/material/Grow';
import Box from '@mui/material/Box';

const StyledContainer = styled(Grid)(({ theme }) => ({
  position: 'absolute',
  top: theme.spacing(3),
  left: theme.spacing(3),
  marginTop: -5,
  maxWidth: 416,
  padding: `0px 12px 12px ${theme.spacing(5)}`,
  borderRadius: theme.spacing(0.5),
  border: `1px solid rgba(4, 78, 243, 0.5)`,
  backgroundColor: '#fff',
}));

const StyledInfoIcon = styled(InfoOutlinedIcon)(() => ({
  fontSize: 26,
}));

const StyledGrow = styled(Grow)(() => ({
  fontSize: 26,
  transformOrigin: '0 0 0',
}));

const StyledInfoButton = styled(IconButton)(({ theme }) => ({
  borderRadius: theme.spacing(0.5),
  padding: 5,
  backgroundColor: theme.palette.common.white,
  border: 'unset',
  boxShadow: 'none',
  [`&:hover`]: {
    backgroundColor: theme.palette.common.white,
    border: 'unset',
  },
}));

const TypeColorIndicator = ({
  backgroundColor,
  isRollup,
}: {
  backgroundColor: string;
  isRollup: boolean;
}) => {
  const TypeColor = styled(Grid)(() => ({
    height: 16,
    width: 16,
    borderRadius: '50%',
    border: '1px solid rgba(0, 0, 0, 0.8);',
    backgroundColor: backgroundColor,
  }));

  const TypeColorRollUp = styled(TypeColor)(() => ({
    borderRadius: '4px',
  }));

  if (isRollup) {
    return <TypeColorRollUp />;
  }

  return <TypeColor />;
};

const MoreInfo = () => {
  const [grow, setGrow] = useState(false);

  const TypeLabel = ({ type }: { type: string }) => (
    <Grid item>
      <Grid container spacing={1} alignItems="center">
        <Grid item>
          <TypeColorIndicator
            backgroundColor={getNodeColor(type)}
            isRollup={type === NodeColors.rollup}
          />
        </Grid>
        <Grid item>
          <Typography variant="caption" color="text">
            {type !== NodeColors.rollup ? type : 'Expandable'}
          </Typography>
        </Grid>
      </Grid>
    </Grid>
  );

  return (
    <Box onMouseLeave={() => setGrow(false)}>
      <StyledInfoButton
        aria-describedby="show-info"
        id="show-info"
        onMouseEnter={() => setGrow(true)}
      >
        <StyledInfoIcon color="primary" />
      </StyledInfoButton>
      <StyledGrow in={grow}>
        <StyledContainer container spacing={1.5}>
          <Grid item xs={12}>
            <Typography variant="body2" color="text">
              Scroll/pinch to zoom in and out.
            </Typography>
          </Grid>
          <Grid item xs={12}>
            <Grid container flexDirection="column" spacing={1.5}>
              <Grid item>
                <Typography variant="body2" maxWidth={360} color="text">
                  Click any target to see its details. Double click an
                  expandable to expand it.
                </Typography>
              </Grid>
              <Grid item flexWrap="wrap" minWidth={360}>
                <Grid container>
                  <Grid item xs={6}>
                    <Grid container flexDirection="column" spacing={1}>
                      {Object.values(NodeColors).map((type, index, arr) => {
                        return index < (arr.length + 1) / 2 ? (
                          <TypeLabel type={type} key={type} />
                        ) : null;
                      })}
                    </Grid>
                  </Grid>
                  <Grid item xs={6}>
                    <Grid container flexDirection="column" spacing={1}>
                      {Object.values(NodeColors).map((type, index, arr) => {
                        return index >= (arr.length + 1) / 2 ? (
                          <TypeLabel type={type} key={type} />
                        ) : null;
                      })}
                      <TypeLabel type="Other target types" />
                    </Grid>
                  </Grid>
                </Grid>
              </Grid>
            </Grid>
          </Grid>
        </StyledContainer>
      </StyledGrow>
    </Box>
  );
};

export default MoreInfo;
