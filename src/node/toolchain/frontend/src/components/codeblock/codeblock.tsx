/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useState } from 'react';
import Ansi from 'ansi-to-react';
import IconButton from '@mui/material/IconButton';
import FileCopy from '@mui/icons-material/FileCopy';
import CloseIcon from '@mui/icons-material/Close';
import Grid from '@mui/material/Grid';
import Snackbar from '@mui/material/Snackbar';
import Collapse from '@mui/material/Collapse';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import Box from '@mui/material/Box';

import { styled } from '@mui/material/styles';

type CodeBlockProps = {
  children: string;
  convertAnsi?: boolean;
};

const StyledCollapse = styled(Collapse, { shouldForwardProp: prop => prop !== 'hasBottomPadding' })<{
  hasBottomPadding?: boolean;
}>(({ theme, hasBottomPadding }) => ({
  lineBreak: 'anywhere',
  margin: 0,
  padding: `${theme.spacing(3)} ${theme.spacing(6)} ${theme.spacing(3)} ${theme.spacing(3)}`,
  border: 0,
  borderRadius: theme.spacing(1),
  whiteSpace: 'pre-wrap',
  backgroundColor: 'rgba(0, 169, 183, 0.08)',
  fontFamily: 'Fira Code, sans-serif',
  fontStyle: 'normal',
  fontSize: 14,
  fontWeight: 400,
  ...(hasBottomPadding ? { paddingBottom: theme.spacing(5) } : {}),
}));
const CodeBlockBox = StyledCollapse.withComponent(Box);
const StyledBoxExpand = styled(Box)(() => ({
  position: 'absolute',
  display: 'flex',
  justifyContent: 'center',
  width: '100%',
  background: 'linear-gradient(180deg, rgba(235, 249, 250, 0) 0%, #EBF9FA 100%);',
  bottom: 0,
}));
const StyledIconButton = styled(IconButton)(({ theme }) => ({
  padding: 0,
  position: 'absolute',
  top: theme.spacing(3),
  right: theme.spacing(3),
}));
const StyledCopyIcon = styled(FileCopy)(() => ({
  fontSize: 18,
}));
const StyledButtonExpand = styled(IconButton)(({ theme }) => ({
  top: 16,
  width: 80,
  height: 32,
  background: theme.palette.common.white,
  borderRadius: 816,
}));

const CodeBlock = ({ children, convertAnsi }: CodeBlockProps) => {
  const [open, setOpen] = useState<boolean>(false);
  const nonExpandedMaxLength = 300;
  const shouldShowExpand = children.length > nonExpandedMaxLength;
  const [expanded, setExpanded] = useState<boolean>(false);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setOpen(true);
  };

  const mainContent = convertAnsi ? <Ansi>{children}</Ansi> : children;

  const expandIcon = expanded ? <KeyboardArrowUpIcon color="primary" /> : <KeyboardArrowDownIcon color="primary" />;
  const labelText = expanded ? 'Collapse text' : 'Expand text';
  const toggleState = () => setExpanded(!expanded);

  const collapsedHeight = shouldShowExpand ? '8em' : '0';

  const CopyButton = () => (
    <StyledIconButton onClick={() => copyToClipboard(children)} aria-label="Copy text" size="large">
      <StyledCopyIcon color="primary" />
    </StyledIconButton>
  );

  return (
    <>
      {shouldShowExpand ? (
        <Box position="relative">
          <StyledCollapse in={expanded} collapsedSize={collapsedHeight} component="pre" hasBottomPadding={true}>
            <Grid container>
              <Grid item xs={12}>
                {mainContent}
              </Grid>
              <CopyButton />
            </Grid>
          </StyledCollapse>
          <StyledBoxExpand>
            <StyledButtonExpand onClick={toggleState} aria-label={labelText} size="large">
              {expandIcon}
            </StyledButtonExpand>
          </StyledBoxExpand>
        </Box>
      ) : (
        <Box position="relative">
          <CodeBlockBox component="pre" hasBottomPadding={false}>
            <Grid container>
              <Grid item xs={12}>
                {mainContent}
              </Grid>
              <CopyButton />
            </Grid>
          </CodeBlockBox>
        </Box>
      )}
      <Snackbar
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        autoHideDuration={5000}
        open={open}
        onClose={() => setOpen(false)}
        message="Copied"
        action={
          <IconButton size="small" aria-label="close" color="inherit" onClick={() => setOpen(false)}>
            <CloseIcon />
          </IconButton>
        }
      />
    </>
  );
};

export default CodeBlock;
