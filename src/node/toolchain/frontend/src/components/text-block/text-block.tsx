/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useState } from 'react';
import IconButton from '@mui/material/IconButton';
import Grid from '@mui/material/Grid';
import Collapse from '@mui/material/Collapse';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import Box from '@mui/material/Box';
import { styled } from '@mui/material/styles';

type TextBlockProps = {
  children: JSX.Element;
  showExpand: boolean;
};

const TextBlockContainer = styled(Box)(({ theme }) => ({
  position: 'relative',
  marginBottom: theme.spacing(1),
}));

const StyledCollapse = styled(Collapse)(({ theme }) => ({
  margin: 0,
  padding: theme.spacing(3),
  border: '1px solid transparent',
  borderRadius: theme.spacing(1),
  whiteSpace: 'pre-wrap',
  backgroundColor: theme.palette.grey[50],
  paddingBottom: theme.spacing(5),
}));

const ExpandButton = styled(IconButton)(({ theme }) => ({
  top: 16,
  width: 80,
  height: 32,
  background: theme.palette.common.white,
  borderRadius: 816,
}));

const StyledTextBlock = styled(Box)(({ theme }) => ({
  margin: 0,
  padding: theme.spacing(3),
  border: '1px solid transparent',
  borderRadius: theme.spacing(1),
  whiteSpace: 'pre-wrap',
  backgroundColor: theme.palette.grey[50],
}));

const ExpandButtonContainer = styled(Box)(() => ({
  position: 'absolute',
  display: 'flex',
  justifyContent: 'center',
  width: '100%',
  background: 'linear-gradient(180deg, rgba(245, 245, 245, 0) 0%, #F5F5F5 100%)',
  bottom: 0,
}));

const TextBlock = ({ children, showExpand = false }: TextBlockProps) => {
  const [expanded, setExpanded] = useState<boolean>(false);
  const expandIcon = expanded ? <KeyboardArrowUpIcon color="primary" /> : <KeyboardArrowDownIcon color="primary" />;
  const labelText = expanded ? 'Collapse text' : 'Expand text';

  const toggleExpand = () => setExpanded(!expanded);

  return showExpand ? (
    <TextBlockContainer>
      <StyledCollapse in={expanded} collapsedSize="8em" component="pre" timeout="auto">
        <Grid container>
          <Grid item xs={12}>
            {children}
          </Grid>
        </Grid>
      </StyledCollapse>
      <ExpandButtonContainer>
        <ExpandButton onClick={toggleExpand} aria-label={labelText} size="large">
          {expandIcon}
        </ExpandButton>
      </ExpandButtonContainer>
    </TextBlockContainer>
  ) : (
    <StyledTextBlock>{children}</StyledTextBlock>
  );
};

export default TextBlock;
