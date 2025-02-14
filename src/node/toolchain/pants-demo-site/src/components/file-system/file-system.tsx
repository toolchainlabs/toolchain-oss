/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { useState } from 'react';
import { styled } from '@mui/material/styles';
import Box from '@mui/material/Box';
import CloseIcon from '@mui/icons-material/Close';
import Grid from '@mui/material/Grid';
import FormControl from '@mui/material/FormControl';
import Input from '@mui/material/Input';
import InputAdornment from '@mui/material/InputAdornment';
import Search from '@mui/icons-material/Search';
import IconButton from '@mui/material/IconButton';

import FileSystemUnit from './file-system-unit';
import SearchResults from '../search-results';

const StyledBox = styled(Box)(({ theme }) => ({
  backgroundColor: theme.palette.common.white,
  borderRadius: theme.spacing(1),
  padding: theme.spacing(3),
  height: '100%',
}));

const StyledIconButton = styled(IconButton)(({ theme }) => ({
  color: theme.palette.text.secondary,
  position: 'absolute',
  top: 0,
  right: 4.5,
  padding: 0,
}));
const StyledGridItem = styled(Grid)(() => ({
  overflowY: 'scroll',
  scrollbarWidth: 'none',
  height: 'calc(100% - 24px)',
  [`&::-webkit-scrollbar`]: {
    display: 'none',
  },
  position: 'relative',
}));
const StyledGradient = styled('div')(() => ({
  height: '40px',
  background:
    'linear-gradient(180deg, rgba(255, 255, 255, 0) 0%, #FFFFFF 100%)',
  width: '100%',
  position: 'absolute',
  bottom: '-40px',
  pointerEvents: 'none',
}));

const FileSystem = () => {
  const [isSearchActive, setIsSearchActive] = useState<boolean>(false);
  const [searchParam, setSearchParam] = useState<string>('');

  const focusSearch = () => {
    setIsSearchActive(true);
  };

  const onInputHandler = (e: React.ChangeEvent<HTMLInputElement>) =>
    setSearchParam(e.target.value);

  const afterItemSelect = () => {
    setIsSearchActive(false);
    setSearchParam('');
  };

  const cancelSearch = () => {
    setIsSearchActive(false);
    setSearchParam('');
  };

  const shouldShowSearchCancel = isSearchActive || !!searchParam;

  return (
    <StyledBox>
      <Grid
        container
        spacing={2}
        position="relative"
        alignItems="flex-start"
        height="100%"
      >
        <Grid item xs={12}>
          <FormControl variant="standard" fullWidth>
            <Input
              id="search-box"
              placeholder="Search a package, node..."
              onFocus={focusSearch}
              value={searchParam}
              name="password"
              autoComplete="off"
              type="text"
              onChange={onInputHandler}
              startAdornment={
                <InputAdornment position="start">
                  <Search color="primary" />
                </InputAdornment>
              }
            />
            {shouldShowSearchCancel && (
              <StyledIconButton onClick={cancelSearch}>
                <CloseIcon />
              </StyledIconButton>
            )}
          </FormControl>
        </Grid>
        <StyledGridItem item xs={12}>
          {isSearchActive ? (
            <SearchResults
              searchParam={searchParam}
              afterItemSelect={afterItemSelect}
            />
          ) : (
            <FileSystemUnit fullName="" />
          )}
        </StyledGridItem>
        <StyledGradient />
      </Grid>
    </StyledBox>
  );
};

export default FileSystem;
