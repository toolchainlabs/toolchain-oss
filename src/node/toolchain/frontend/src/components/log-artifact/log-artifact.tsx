/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useState, useEffect, useRef } from 'react';
import { useQueryParams, NumberParam } from 'use-query-params';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import ClickAwayListener from '@mui/material/ClickAwayListener';
import Ansi from 'ansi-to-react';
import { styled } from '@mui/material/styles';

import { useLocation, useNavigate, useNavigationType } from 'react-router-dom';

import { Artifact, LogArtifactContent } from 'common/interfaces/build-artifacts';
import ArtifactCard from 'pages/builds/artifact-card';

const LogArtifactContainer = styled(Grid)(({ theme }) => ({
  backgroundColor: 'rgba(0, 169, 183, 0.08)',
  padding: `${theme.spacing(2.5)} 0`,
}));

const ItemIndex = styled(Grid)(() => ({
  cursor: 'pointer',
  userSelect: 'none',
}));

const CodeRow = styled(Ansi)(({ theme }) => ({
  fontFamily: 'Fira Code, sans-serif',
  fontSize: 14,
  fontStyle: 'normal',
  fontWeight: 400,
  lineHeight: 1.5,
  color: theme.palette.text.primary,
}));

const SelectedIndex = styled(Typography)(({ theme }) => ({
  color: theme.palette.warning.main,
}));

const RowIndex = styled(Typography)(({ theme }) => ({
  color: theme.palette.text.disabled,
}));

const LogArtifact = ({ artifact }: { artifact: Artifact<LogArtifactContent> }) => {
  const [startingLine, setStartingLine] = useState<number>(-1);
  const [hoveredLine, setHoveredLine] = useState<number>(-1);
  const location = useLocation();
  const navigate = useNavigate();
  const navigationType = useNavigationType();

  const [query, updateQuery] = useQueryParams({
    firstLine: NumberParam,
    lastLine: NumberParam,
  });

  const linesArrayRef = useRef([]);

  const contentLines = artifact.content.split('\n');

  const firstMarkedLineIndex = +query.firstLine || -1;
  const lastMarkedLineIndex = +query.lastLine || -1;

  useEffect(() => {
    const shouldScrollToElement = navigationType !== 'REPLACE';
    const markedLineWrapper = linesArrayRef.current[firstMarkedLineIndex];
    if (markedLineWrapper && shouldScrollToElement) {
      markedLineWrapper.scrollIntoView({ behavior: 'smooth' });
    }
  }, [location.hash, firstMarkedLineIndex, navigationType]);

  const onMouseUpHandler = async () => {
    if (firstMarkedLineIndex < 0 && startingLine < 0) {
      return;
    }

    if (startingLine < 0 || hoveredLine < 0) {
      updateQuery({ ...query, firstLine: undefined, lastLine: undefined });
      return;
    }

    const firstLine = startingLine <= hoveredLine ? startingLine : hoveredLine;
    const lastLine = startingLine > hoveredLine ? startingLine : hoveredLine;

    const newQueryParams = new URLSearchParams(location.search);
    newQueryParams.set('firstLine', firstLine.toString());
    if (firstLine !== lastLine) {
      newQueryParams.set('lastLine', lastLine.toString());
    } else {
      newQueryParams.delete('lastLine');
    }

    navigate({ pathname: location.pathname, search: `?${newQueryParams.toString()}` }, { replace: true });
  };

  const onMouseHoverHandler = (index: number) => {
    setHoveredLine(index);
  };

  const onMouseDownHandler = (index: number) => {
    if (hoveredLine > 0) {
      setStartingLine(index);
    }
  };

  const isLineHighlighted = (index: number) => {
    if (startingLine < 0) {
      return (
        (lastMarkedLineIndex < 0 && index === firstMarkedLineIndex) ||
        (index >= firstMarkedLineIndex && index <= lastMarkedLineIndex)
      );
    }

    const firstLine = startingLine <= hoveredLine ? startingLine : hoveredLine;
    const lastLine = startingLine >= hoveredLine ? startingLine : hoveredLine;

    return index >= firstLine && index <= lastLine;
  };

  const getActiveClassesArray = (index: number) => {
    const isHighlighted = isLineHighlighted(index);

    const hasBorders = isHighlighted && startingLine < 0;
    const isFirstSelectedRow = startingLine < 0 && index === firstMarkedLineIndex;
    const isLastSelectedRow =
      startingLine < 0 &&
      (index === lastMarkedLineIndex || (lastMarkedLineIndex < 0 && index === firstMarkedLineIndex));

    const transparentBorder = '1px solid transparent';

    const RowContainer = styled(Grid)(({ theme }) => ({
      padding: `${theme.spacing(0.5)} ${theme.spacing(3)}`,
      border: transparentBorder,
      [`&:hover`]: {
        background: 'linear-gradient(0deg, rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0.9)), #FF9800;',
        [`& p`]: {
          color: theme.palette.warning.main,
        },
      },
      background: isHighlighted
        ? 'linear-gradient(0deg, rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0.9)), #FF9800;'
        : '',
      borderLeft: hasBorders ? `1px solid ${theme.palette.warning.main}` : transparentBorder,
      borderRight: hasBorders ? `1px solid ${theme.palette.warning.main}` : transparentBorder,
      borderTop: isFirstSelectedRow ? `1px solid ${theme.palette.warning.main}` : transparentBorder,
      borderBottom: isLastSelectedRow ? `1px solid ${theme.palette.warning.main}` : transparentBorder,
    }));

    return RowContainer;
  };

  const assignElementRef = (element: HTMLDivElement, index: number) => {
    linesArrayRef.current[index + 1] = element;
  };

  return (
    <ClickAwayListener onClickAway={() => onMouseUpHandler()}>
      <div>
        <ArtifactCard hideAllHeaders>
          <LogArtifactContainer container direction="column">
            {contentLines.map((row, index) => {
              const lineId = index + 1;
              const MyGrid = getActiveClassesArray(lineId);
              const isRowSelected = isLineHighlighted(lineId);
              return (
                <MyGrid item key={lineId}>
                  <Grid container spacing={3}>
                    <ItemIndex
                      item
                      id={`line${lineId}`}
                      ref={element => assignElementRef(element, lineId)}
                      onMouseDown={() => onMouseDownHandler(lineId)}
                      onMouseEnter={() => onMouseHoverHandler(lineId)}
                      onMouseUp={() => onMouseUpHandler()}
                    >
                      {isRowSelected ? (
                        <SelectedIndex variant="code1">{lineId}</SelectedIndex>
                      ) : (
                        <RowIndex variant="code1">{lineId}</RowIndex>
                      )}
                    </ItemIndex>

                    <Grid item xs>
                      <CodeRow>{row}</CodeRow>
                    </Grid>
                  </Grid>
                </MyGrid>
              );
            })}
          </LogArtifactContainer>
        </ArtifactCard>
      </div>
    </ClickAwayListener>
  );
};

export default LogArtifact;
