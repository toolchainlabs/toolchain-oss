/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { styled } from '@mui/material/styles';
import Grid from '@mui/material/Grid';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import exampleRepos from '../example-repos';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

type SeeExamplesContainerType = {
  onBackBtnClick: () => void;
};

const SeeExamplesWrapper = styled(Grid)(() => ({
  position: 'relative',
}));

const GoBackButton = styled(Button)(() => ({
  position: 'absolute',
  top: 24,
  left: 24,
}));

const ExamplesList = styled(Grid)(() => ({
  overflowY: 'auto',
  border: `1px solid rgba(0, 169, 183, 0.5)`,
  backgroundColor: '#fff',
  borderRadius: 8,
  maxHeight: 520,
  flexWrap: 'nowrap',
  width: '100%',
  '&::-webkit-scrollbar, & *::-webkit-scrollbar': {
    width: 5,
  },
  '&::-webkit-scrollbar-thumb, & *::-webkit-scrollbar-thumb': {
    borderRadius: 8,
    backgroundColor: 'rgba(0, 169, 183, 0.4)',
  },
}));

const ExampleElement = styled('a')(({ theme }) => ({
  display: 'flex',
  width: '100%',
  cursor: 'pointer',
  color: theme.palette.text.primary,
  ['&:hover']: {
    backgroundColor: 'rgba(0, 169, 183, 0.1)',
  },
}));

const ExampleImage = styled('img')(() => ({
  height: 80,
  width: 80,
}));

const ExampleText = styled('div')(() => ({
  paddingLeft: 24,
  paddingTop: 28,
  paddingBottom: 28,
  flex: 1,
}));

const GoBackIcon = styled(ArrowBackIcon)(() => ({
  height: 18,
  width: 18,
  marginRight: 4,
}));

const SeeExamplesContainer = ({ onBackBtnClick }: SeeExamplesContainerType) => {
  const getRepoPageUrl = (repoUrl: string) => {
    const origin = window.location.origin;

    return `${origin}/app/repo${repoUrl}`;
  };

  return (
    <SeeExamplesWrapper
      container
      flexDirection="column"
      alignItems="center"
      spacing={3}
    >
      <GoBackButton color="primary" onClick={onBackBtnClick}>
        <GoBackIcon height={12} /> go back
      </GoBackButton>
      <Grid item>
        <Typography variant="h3">Example repos</Typography>
      </Grid>
      <Grid item width="100%">
        <ExamplesList
          container
          flexDirection="column"
          alignItems="center"
          id="examples-list"
        >
          {exampleRepos.map(example => {
            const fullName = `/${example.organizationName}/${example.repoName}`;
            return (
              <Grid item key={fullName} width="100%">
                <ExampleElement href={getRepoPageUrl(fullName)}>
                  <ExampleImage src={example.imgUrl} />
                  <ExampleText>
                    <Typography variant="body1">{fullName}</Typography>
                  </ExampleText>
                </ExampleElement>
              </Grid>
            );
          })}
        </ExamplesList>
      </Grid>
    </SeeExamplesWrapper>
  );
};

export default SeeExamplesContainer;
