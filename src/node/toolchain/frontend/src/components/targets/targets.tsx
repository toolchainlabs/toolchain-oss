/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useState } from 'react';

import Grid from '@mui/material/Grid';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';

import { ArtifactProps, TargetsContent } from 'common/interfaces/build-artifacts';
import ArtifactCard from 'pages/builds/artifact-card';
import { styled } from '@mui/material/styles';

const DataContainer = styled(Grid)(() => ({
  backgroundColor: 'rgba(0, 169, 183, 0.08)',
  marginTop: 16,
  paddingLeft: 24,
  paddingRight: 24,
  paddingTop: 18,
  paddingBottom: 16,
  borderRadius: '8px',
}));

const NestedDataLabel = styled('div')(() => ({
  display: 'flex',
  flexGrow: 1,
  alignItems: 'center',
  justifyContent: 'space-between',
  cursor: 'pointer',
  marginTop: 2,
  marginBottom: 2,
}));

const BoldText = styled('span')(() => ({
  fontWeight: 700,
}));

const NestedDataDots = styled('div')(() => ({
  height: 12,
  borderTop: '1px dashed rgba(0, 169, 183, 0.5)',
  flex: 1,
  marginLeft: 12,
  alignSelf: 'flex-end',
}));

const NestedDataFolderLabel = styled(NestedDataLabel)(() => ({
  marginTop: 6,
}));

const NestedDataNumOfItems = styled(Typography)(({ theme }) => ({
  color: theme.palette.text.secondary,
  marginLeft: 12,
}));

const NestedDataSubFolder = styled('div')(() => ({
  marginLeft: 12,
  borderLeft: `1px solid rgba(0, 169, 183, 0.5)`,
  paddingLeft: 8,
}));

const StyledTextField = styled(TextField)(() => ({
  width: '100%',
  '& :after': {
    display: 'none',
  },
}));

export type RecursionFileProps = {
  name: string;
  indexOfSearchedSubstr: number;
};

export type RecursionBottomFolderProps = RecursionFileProps[];

export type RecursionStandardFolderProps = {
  content: Array<RecursionBottomFolderProps | RecursionStandardFolderProps | RecursionFileProps | null>;
  folderName?: string;
  indexOfSearchedSubstr?: number;
  length: number;
};

export type FilteredDataType = RecursionFileProps | RecursionBottomFolderProps | RecursionStandardFolderProps | null;

export const filterSrcData = (
  data: any,
  searchFilter: string
): RecursionFileProps | RecursionBottomFolderProps | RecursionStandardFolderProps | null => {
  if (!data) {
    return null;
  }
  const newData: Array<RecursionFileProps | RecursionStandardFolderProps | RecursionBottomFolderProps | null> = [];

  const isFile = typeof data === 'object' && !Array.isArray(data) && data.filename;

  if (isFile) {
    const indexOfSearchFilter = data.filename.indexOf(searchFilter);
    if (indexOfSearchFilter >= 0) {
      return {
        name: data.filename,
        indexOfSearchedSubstr: indexOfSearchFilter,
      };
    }
    return null;
  }
  if (Array.isArray(data)) {
    data.forEach(el => {
      const result = filterSrcData(el, searchFilter);
      if (result) {
        newData.push(result);
      }
    });
    return newData.length > 0 ? (newData as RecursionBottomFolderProps) : null;
  }
  // Based on data we get from the server, we have difference in displaying folders with files only and folders with subfolders inside
  const isHigherLevelFolder = typeof data === 'object' && !Array.isArray(data) && typeof data.filename !== 'string';
  if (isHigherLevelFolder) {
    let length = 0;
    Object.keys(data).forEach(key => {
      const results = filterSrcData(data[key], searchFilter);
      const indexOf = key.indexOf(searchFilter);

      if (results || indexOf >= 0) {
        let resultsLength = (results as RecursionStandardFolderProps | RecursionFileProps[])?.length;
        resultsLength = resultsLength || 0;
        newData.push({
          content: Array.isArray(results) ? results : (results as RecursionStandardFolderProps)?.content,
          folderName: key,
          indexOfSearchedSubstr: indexOf,
          length: resultsLength,
        });
        length += resultsLength;
      }
    });
    return {
      content: newData,
      length,
    };
  }
  return newData.length > 0 ? (newData as RecursionBottomFolderProps) : null;
};

export const NestedDataTable = ({
  label,
  numOfItems = 0,
  children = null,
  indexOfMatch = -1,
  matchLength = 0,
  isFolder = false,
}: {
  label: string;
  numOfItems?: number;
  indexOfMatch?: number;
  matchLength?: number;
  isFolder?: boolean;
  children?: any;
}) => {
  const [showChildren, setShowChildren] = useState(true);
  const LabelComponent = children ? NestedDataFolderLabel : NestedDataLabel;

  return (
    <>
      {indexOfMatch >= 0 || children ? (
        <LabelComponent onClick={() => setShowChildren(prev => !prev)}>
          {isFolder && showChildren ? <ExpandMoreIcon /> : null}
          {isFolder && !showChildren ? <ChevronRightIcon /> : null}
          {indexOfMatch >= 0 ? (
            <Typography variant="body1">
              {label.substr(0, indexOfMatch)}
              <BoldText>{label.substr(indexOfMatch, matchLength)}</BoldText>
              {label.substr(indexOfMatch + matchLength)}
            </Typography>
          ) : (
            <Typography variant="body1">{label}</Typography>
          )}

          <NestedDataDots />
          {isFolder ? (
            <NestedDataNumOfItems variant="caption">
              {numOfItems}
              {numOfItems === 1 ? ' item' : ' items'}
            </NestedDataNumOfItems>
          ) : null}
        </LabelComponent>
      ) : null}
      {children && showChildren ? <NestedDataSubFolder>{children}</NestedDataSubFolder> : null}
    </>
  );
};

export const createNestedTable = (data: FilteredDataType, matchLength: number): any => {
  const isFile = typeof data === 'object' && !Array.isArray(data) && (data as RecursionFileProps).name;
  if (isFile) {
    return (
      <NestedDataTable
        label={(data as RecursionFileProps).name}
        indexOfMatch={(data as RecursionFileProps).indexOfSearchedSubstr}
        matchLength={matchLength}
        key={(data as RecursionFileProps).name}
      />
    );
  }
  const isHigherLevelFolder =
    typeof data === 'object' && !Array.isArray(data) && (data as RecursionStandardFolderProps).folderName;
  if (isHigherLevelFolder) {
    const myChildren = (data as RecursionStandardFolderProps).content;
    return (
      <NestedDataTable
        label={(data as RecursionStandardFolderProps).folderName}
        numOfItems={(data as RecursionStandardFolderProps).length}
        indexOfMatch={(data as RecursionStandardFolderProps).indexOfSearchedSubstr}
        matchLength={matchLength}
        key={(data as RecursionStandardFolderProps).folderName}
        isFolder
      >
        {myChildren?.length > 0 ? myChildren.map(element => createNestedTable(element, matchLength)) : null}
      </NestedDataTable>
    );
  }
  const isBottomLevelFolder = Array.isArray(data);
  if (isBottomLevelFolder) {
    return (data as RecursionBottomFolderProps).map(element => createNestedTable(element, matchLength));
  }

  return null;
};

function Targets({ artifact }: ArtifactProps<TargetsContent>) {
  const [searchFilter, setSearchFilter] = useState('');

  const filteredData = filterSrcData(artifact.content, searchFilter);
  const numOfFiles = (filteredData as RecursionFileProps)?.name
    ? 1
    : (filteredData as RecursionBottomFolderProps | RecursionStandardFolderProps)?.length || 0;

  return (
    <ArtifactCard hideAllHeaders>
      <Grid container direction="column">
        <Grid item>
          <Typography variant="h4">
            {numOfFiles} {numOfFiles === 1 ? 'file ' : 'files '} in total
          </Typography>
        </Grid>
        <Grid item>
          <form noValidate autoComplete="off">
            <StyledTextField
              label="Search file name"
              id="search-files"
              color="secondary"
              onChange={e => setSearchFilter(e.target.value)}
              error={false}
            />
          </form>
        </Grid>
        {numOfFiles ? (
          <DataContainer item>
            {(filteredData as RecursionFileProps)?.name || Array.isArray(filteredData)
              ? createNestedTable(filteredData, searchFilter.length)
              : (filteredData as RecursionStandardFolderProps)?.content.map(
                  (el: RecursionStandardFolderProps | RecursionBottomFolderProps | RecursionFileProps) =>
                    createNestedTable(el, searchFilter.length)
                )}
          </DataContainer>
        ) : null}
      </Grid>
    </ArtifactCard>
  );
}

export default Targets;
