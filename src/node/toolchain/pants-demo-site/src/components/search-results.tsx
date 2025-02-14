/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { styled } from '@mui/material/styles';
import { useSelector, useDispatch } from 'react-redux';
import NodeSet from '../models/NodeSet';
import { GlobalState } from '../store/types';
import { nodeSelected, nodeFocused } from '../store/nodeSlice';
import { visibleGraphExpandedDeep } from '../store/visibleGraphSlice';
import { findParentAddress, findSearchSegment } from '../models/utils';
import Typography from '@mui/material/Typography';
import { Grid } from '@mui/material';

type SeatchResultsType = {
  searchParam: string;
  afterItemSelect: () => void;
};

const StyledNoResultsMessage = styled(Typography)(({ theme }) => ({
  color: theme.palette.text.secondary,
}));

const StyledNameItem = styled(Grid)(() => ({
  cursor: 'pointer',
  overflowWrap: 'break-word',
  marginBottom: 3,
  display: 'flex',
  justifyContent: 'flex-start',
  position: 'relative',
  [`&:hover`]: {
    textDecoration: 'none',
  },
}));

const StyledName = styled(Typography)(({ theme }) => ({
  wordBreak: 'break-word',
  [`&:hover`]: {
    color: theme.palette.primary.light,
  },
}));

const MatchedSegment = styled('span')(() => ({ fontWeight: 'bold' }));

const SearchResults = ({ searchParam, afterItemSelect }: SeatchResultsType) => {
  const hd = useSelector(
    (state: GlobalState) => state.hierarchicalDigraph.graph
  );

  const dispatch = useDispatch();

  const allNodes = hd?.allRolledUpNodes || new NodeSet();

  const onNodeSelect = (nodeAddress: string) => {
    dispatch(nodeSelected(nodeAddress));
    dispatch(nodeFocused(nodeAddress));
    dispatch(visibleGraphExpandedDeep(findParentAddress(nodeAddress)));
    afterItemSelect();
  };

  const filteredArray = Array.from(allNodes)
    .map(node => ({
      ...node,
      searchPosition: node.address
        .toLocaleLowerCase()
        .search(searchParam.toLowerCase()),
    }))
    .filter(enhancedNode => enhancedNode.searchPosition >= 0);

  const hasResults = filteredArray.length;
  return (
    <>
      {hasResults ? (
        filteredArray.map(node => {
          const searchSegments = findSearchSegment(node.address, searchParam, {
            caseUnsensitive: true,
          });
          return (
            <StyledNameItem
              key={node.address}
              onClick={() => onNodeSelect(node.address)}
              className="search-result-item"
            >
              <StyledName variant="body2" color="text">
                {searchSegments[0]}
                <MatchedSegment>{searchSegments[1]}</MatchedSegment>
                {searchSegments[2]}
              </StyledName>
            </StyledNameItem>
          );
        })
      ) : (
        <StyledNoResultsMessage variant="body2">
          There is no results for {`"${searchParam}"`}
        </StyledNoResultsMessage>
      )}
    </>
  );
};

export default SearchResults;
