/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { useState, useEffect } from 'react';
import { useDispatch } from 'react-redux';
import { styled } from '@mui/material/styles';
import CloseIcon from '@mui/icons-material/Close';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import Avatar from '@mui/material/Avatar';
import Grid from '@mui/material/Grid';
import LinearProgress from '@mui/material/LinearProgress';
import Paper from '@mui/material/Paper';
import Link from '@mui/material/Link';
import Button from '@mui/material/Button';
import Snackbar from '@mui/material/Snackbar';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import DependencyGraph from '../dependency-graph';
import HierarchicalDigraph from '../models/hierarchical-digraph';
import VisibleGraph from '../models/visible-graph';
import {
  getEdgesFromInputData,
  initialAddressFormat,
} from '../data-structure-utils';
import FileSystem from './file-system/file-system';
import TargetDescription from './target-description/target-description';
import { hierarchicalDigraphSet } from '../store/hierarchicalDigraphSlice';
import { globalTypesMapSet } from '../store/globalTypesSlice';
import { visibleGraphSet } from '../store/visibleGraphSlice';
import { fetchResults, RepoState } from '../api-calls/results-data';
import { LeafNode } from '../models/Node';
import Background from './background/background';
import cube from '../assets/cube.png';
import Footer from './footer/footer';
import ProcessingFailed from './processing-failed/processing-failed';
import SeeExamplesContainer from './see-examples-container';
import Header from './header';
import AdditionalExplanationCard from './additional-explanation-card';
import { errorPageUrl } from '../utils';
import * as Sentry from '@sentry/react';

const StyledLink = styled(Link)(({ theme }) => ({
  display: 'block',
  margin: '0 auto',
  maxWidth: 'fit-content',
  borderRadius: 8,
  border: `1px solid rgba(4, 78, 243, 0.5)`,
  backgroundColor: theme.palette.background.default,
  padding: '0 8px 0 0',
}));

const GraphContainer = styled(Grid)(() => ({
  height: '100%',
  borderRadius: 8,
  overflow: 'hidden',
}));

const InfoContainer = styled(Grid)(() => ({
  display: 'flex',
  flexDirection: 'column',
  position: 'relative',
}));

const FileSystemContainer = styled(Grid)(() => ({
  height: '66%',
}));

const DescriptionContainer = styled(Grid)(() => ({
  height: '34%',
}));

const StyledCubeImg = styled('img')(({ theme }) => ({
  '@keyframes rotate': {
    '0%': {
      transform: 'rotate(0deg)',
    },
    '50%': {
      transform: 'rotate(0deg)',
    },
    '100%': {
      transform: 'rotate(180deg)',
    },
  },
  animation: `rotate 2s ${theme.transitions.easing.easeOut} 0s infinite`,
}));

const StyledProcessingText = styled(Typography)(({ theme }) => ({
  '@keyframes colorChange': {
    '0%': {
      color: theme.palette.primary.light,
    },
    '50%': {
      color: theme.palette.primary.main,
    },
    '100%': {
      color: theme.palette.primary.light,
    },
  },
  animation: `colorChange 2s ${theme.transitions.easing.easeOut} 0s infinite`,
}));

const StyledPaper = styled(Paper)(({ theme }) => ({
  border: `1px solid ${theme.palette.grey[200]}`,
  maxWidth: 1200,
  padding: theme.spacing(5),
  borderRadius: theme.spacing(1),
  boxShadow: 'none',
  margin: `${theme.spacing(5)} auto auto auto`,
}));

const StyledOpenInNewIcon = styled(OpenInNewIcon)(() => ({
  marginTop: 6,
}));

const StyledAvatar = styled(Avatar)(({ theme }) => ({
  borderRadius: theme.spacing(1),
}));

const StyledSnackbar = styled(Snackbar)(({ theme }) => ({
  backgroundColor: `rgba(28, 43, 57, 1)`,
  color: theme.palette.common.white,
}));

const StyledCloseIcon = styled(CloseIcon)(({ theme }) => ({
  color: theme.palette.common.white,
}));

const HideOnMobileGridItem = styled(Grid)(({ theme }) => ({
  [theme.breakpoints.down('md')]: {
    display: 'none',
  },
}));

const HideOnDesktopGridItem = styled(Grid)(({ theme }) => ({
  [theme.breakpoints.up('md')]: {
    display: 'none',
  },
}));

const GridTopElement = styled(Grid)(({ theme }) => ({
  marginTop: theme.spacing(5),
  justifyContent: 'center',
  [theme.breakpoints.down('md')]: {
    flexDirection: 'column',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: theme.spacing(20),
    flex: 1,
  },
}));

const MobileMessageContainer = styled(HideOnDesktopGridItem)(() => ({
  margin: '0 auto',
}));

const NotSupportedOnMobileText = styled(Typography)(({ theme }) => ({
  fontFamily: 'Fira Sans',
  fontSize: 18,
  fontWeight: 400,
  lineHeight: '27px',
  letterSpacing: 0,
  textAlign: 'center',
  width: 400,
  [theme.breakpoints.down('sm')]: {
    width: '100%',
    padding: '0 16px',
  },
}));

function Results() {
  const [open, setOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingFailed, setProcessingFailed] = useState(false);
  const [accountName, setAccountName] = useState<string>();
  const [repoName, setRepoName] = useState<string>();
  const [avatarUrl, setAvatarUrl] = useState<string>();
  const [shouldShowExamples, setShouldShowExamples] = useState<boolean>(false);
  const [windowHeight, setWindowHeight] = useState<number>(window.innerHeight);
  const [windowWidth, setWindowWidth] = useState<number>(window.innerWidth);

  const dispatch = useDispatch();

  useEffect(() => {
    const resizeEvent = () => {
      setWindowHeight(window.innerHeight);
      setWindowWidth(window.innerWidth);
    };

    window.addEventListener('resize', resizeEvent);

    return () => window.removeEventListener('resize', resizeEvent);
  });

  const usefulHeight = 0.7;

  const gridHeight = windowHeight * usefulHeight;
  const canvasWidth = windowWidth - 128 - 400;
  const fileSystemWidth = Math.max(windowWidth / 4, 400);

  const isMobile = windowWidth < 900;

  const isFailedOnDesktop = processingFailed && !isMobile;
  const isProcessingOnDesktop = isProcessing && !isMobile;

  const ResultsContainer = styled(Grid)(() => ({
    position: 'relative',
    margin: '0 64px',
    width: 'calc(100% - 128px)',
    height: gridHeight,
  }));

  // eslint-disable-next-line  @typescript-eslint/no-explicit-any
  const unexpectedErrorHandler = (error: any) => {
    Sentry.captureException(error);
    window.location.assign(errorPageUrl);
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(window.location.href);
    setOpen(true);
  };

  useEffect(() => {
    const pathName = window.location.pathname;
    const queryParams = pathName.split('/');
    const accountNameFromParams = queryParams[3];
    const repoNameFromParams = queryParams[4];

    if (!accountNameFromParams) {
      unexpectedErrorHandler('Account name is undefined');
      return;
    }

    if (!repoNameFromParams) {
      unexpectedErrorHandler('Repo name is undefined');
      return;
    }

    setRepoName(repoNameFromParams);
    setAccountName(accountNameFromParams);
  }, []);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const rescheduleDelay = 5000;

        if (!accountName || !repoName) {
          return;
        }

        const origin = window.location.origin;

        const resultsLocation = `${origin}/api/v1/repos/${accountName}/${repoName}/`;

        const results = await fetchResults(resultsLocation);
        const repoState = results.state;

        if (
          repoState === RepoState.PROCESSING ||
          repoState === RepoState.NOT_PROCESSED
        ) {
          setTimeout(fetchData, rescheduleDelay);
          setIsProcessing(true);
          return;
        }

        const targetList = results.target_list;

        if (repoState === RepoState.FAILURE || !targetList) {
          setProcessingFailed(true);
          setIsLoading(false);
          setIsProcessing(false);
          return;
        }

        const edges = getEdgesFromInputData(targetList);
        const hd = new HierarchicalDigraph(
          targetList.map(
            el => new LeafNode(initialAddressFormat(el.address), el.target_type)
          ),
          edges
        );
        const vg = VisibleGraph.initial(hd);

        setAvatarUrl(results?.repo?.avatar);
        dispatch(hierarchicalDigraphSet(hd));
        dispatch(visibleGraphSet(vg));
        dispatch(globalTypesMapSet(hd.leafTypeCounts()));
        setIsLoading(false);
        setIsProcessing(false);
        setProcessingFailed(false);
      } catch (ex) {
        unexpectedErrorHandler(ex);
      }
    };

    fetchData();
  }, [repoName, accountName]);

  useEffect(() => {
    if (repoName && accountName) {
      document.title = `Graph of ${accountName}/${repoName}, powered by Pants`;
    }
  }, [repoName, accountName]);

  const showExamples = () => setShouldShowExamples(true);
  const hideExamples = () => setShouldShowExamples(false);

  if (isFailedOnDesktop) {
    return <ProcessingFailed />;
  } else if (isProcessingOnDesktop) {
    return (
      <Background>
        <Grid
          container
          justifyContent="space-between"
          minHeight="100vh"
          flexDirection="column"
        >
          <Grid item xs={12} flex={1}>
            <Grid container justifyContent="center" alignItems="center">
              <Grid item xs={12} textAlign="center" mt={15} mb={8}>
                <Typography variant="h2" color="text">
                  Graph My Repo
                </Typography>
              </Grid>
              {!shouldShowExamples ? (
                <>
                  <Grid item xs={12}>
                    <Grid
                      container
                      spacing={1}
                      justifyContent="center"
                      alignItems="center"
                    >
                      <Grid item xs={12} textAlign="center">
                        <StyledCubeImg src={cube} alt="Cube" />
                      </Grid>
                      <Grid item xs={12}>
                        <StyledProcessingText
                          variant="h3"
                          color="primary"
                          textAlign="center"
                        >
                          Processing
                        </StyledProcessingText>
                      </Grid>
                    </Grid>
                  </Grid>
                  <Grid item xs={6}>
                    <Grid container justifyContent="center">
                      <Grid item>
                        <Typography
                          variant="body1"
                          textAlign="center"
                          mt={3}
                          maxWidth={588}
                        >
                          This takes a few minutes the first time a repo is
                          analyzed, and the results are cached for future use.
                          This page will refresh with the results when the
                          analysis is complete. Feel free to bookmark it and
                          come back later, or have a look at some examples while
                          you wait.
                        </Typography>
                      </Grid>
                    </Grid>
                  </Grid>
                  <Grid item xs={12} mt={3}>
                    <Grid container justifyContent="center" alignItems="center">
                      <Grid item xs={12} textAlign="center">
                        <Button
                          variant="outlined"
                          color="primary"
                          onClick={showExamples}
                        >
                          see examples
                        </Button>
                      </Grid>
                    </Grid>
                  </Grid>
                  <Grid item xs={12} zIndex={10}>
                    <StyledPaper>
                      <Grid container spacing={3}>
                        <Grid item xs={6}>
                          <Grid container spacing={5}>
                            <Grid item>
                              <Grid container spacing={5}>
                                <Grid item xs={12}>
                                  <Grid container spacing={2}>
                                    <Grid item xs={12}>
                                      <Typography variant="h3">
                                        {`What's happening?`}
                                      </Typography>
                                    </Grid>
                                    <Grid item xs={12} display="flex">
                                      <Typography variant="body1">
                                        {`Toolchain's servers are processing your
                                    repo's code using `}
                                        <Link
                                          href="https://www.pantsbuild.org/"
                                          type="external"
                                          target="_blank"
                                          rel="noopener noreferrer"
                                        >
                                          <strong> Pants</strong>
                                        </Link>
                                        .
                                      </Typography>
                                    </Grid>
                                  </Grid>
                                </Grid>
                                <Grid item>
                                  <Grid container spacing={2}>
                                    <Grid item>
                                      <Typography variant="h3">
                                        What is Pants?
                                      </Typography>
                                    </Grid>
                                    <Grid item>
                                      <Typography variant="body1">
                                        Pants is a state-of-the art software
                                        build system. It installs, configures
                                        and orchestrates the tools used for
                                        tasks such as compiling, testing,
                                        formatting, linting, typechecking and
                                        packaging code. It supports multiple
                                        languages, but is particularly
                                        comprehensive for Python.
                                      </Typography>
                                    </Grid>
                                  </Grid>
                                </Grid>
                              </Grid>
                            </Grid>
                          </Grid>
                        </Grid>
                        <Grid item xs={6}>
                          <Grid container spacing={2}>
                            <Grid item>
                              <Typography variant="h3">
                                Why is this relevant?
                              </Typography>
                            </Grid>
                            <Grid item>
                              <Typography variant="body1">
                                Pants uses static analysis to learn about the
                                structure and dependencies of your codebase.
                                This data allows it to apply fine-grained
                                caching and concurrency, to speed up builds. It
                                also makes this data available for inspection
                                and analysis by users. The site uses this data
                                to visualize your codebase as a graph. In fact,
                                we built this site to demonstrate some of these
                                dependency analysis capabilities.
                              </Typography>
                            </Grid>
                            <Grid item>
                              <Typography variant="body1">
                                {`If you're interested in learning how Pants can
                            streamline and speed up the testing and packaging
                            workflows in your repo, come and `}
                                <Link
                                  href="https://www.pantsbuild.org/docs/getting-help"
                                  type="external"
                                  target="_blank"
                                  rel="noopener noreferrer"
                                >
                                  <strong>chat with us</strong>
                                </Link>
                                !
                              </Typography>
                            </Grid>
                          </Grid>
                        </Grid>
                      </Grid>
                    </StyledPaper>
                  </Grid>
                </>
              ) : (
                <Grid item xs={6} zIndex={10}>
                  <SeeExamplesContainer onBackBtnClick={hideExamples} />
                </Grid>
              )}
            </Grid>
          </Grid>
          <Grid item xs={12} mt={5}>
            <Footer />
          </Grid>
        </Grid>
      </Background>
    );
  } else if (isLoading) {
    return <LinearProgress color="primary" />;
  }

  return (
    <Background>
      <Header copyToClipboard={copyToClipboard} />
      <GridTopElement container spacing={5} sx={{ zIndex: 5 }}>
        <HideOnMobileGridItem
          item
          xs={12}
          alignSelf="center"
          textAlign="center"
        >
          <Typography variant="h2" color="text">
            Graph My Repo
          </Typography>
        </HideOnMobileGridItem>
        <HideOnMobileGridItem item xs={12}>
          <Grid container spacing={1}>
            <Grid item xs={12}>
              <Typography variant="body1" textAlign="center">
                Dependencies and code structure of
              </Typography>
            </Grid>
            <Grid item xs={12}>
              <StyledLink
                type="external"
                target="_blank"
                rel="noopener noreferrer"
                href={`https://github.com/${accountName}/${repoName}`}
              >
                <Grid container spacing={1} alignItems="center">
                  <Grid item>
                    <StyledAvatar src={avatarUrl} />
                  </Grid>
                  <Grid item>
                    <Typography variant="button" color="primary.dark">
                      {accountName}/{repoName}
                    </Typography>
                  </Grid>
                  <Grid item>
                    <StyledOpenInNewIcon color="primary" />
                  </Grid>
                </Grid>
              </StyledLink>
            </Grid>
          </Grid>
        </HideOnMobileGridItem>
        <HideOnMobileGridItem item xs={12}>
          <ResultsContainer container spacing={3}>
            <GraphContainer item xs>
              <DependencyGraph
                canvasWidth={canvasWidth}
                canvasHeight={gridHeight}
              />
            </GraphContainer>
            <InfoContainer item width={fileSystemWidth}>
              <Grid
                container
                flexDirection="column"
                spacing={3}
                height={gridHeight}
              >
                <FileSystemContainer item>
                  <FileSystem />
                </FileSystemContainer>
                <DescriptionContainer item>
                  <TargetDescription />
                </DescriptionContainer>
              </Grid>
            </InfoContainer>
          </ResultsContainer>
        </HideOnMobileGridItem>
        <HideOnMobileGridItem item>
          <AdditionalExplanationCard />
        </HideOnMobileGridItem>
        <MobileMessageContainer item>
          <Grid
            container
            flexDirection="column"
            alignItems="center"
            spacing={3}
          >
            <Grid item>
              <Typography variant="h2" color="text">
                Graph My Repo
              </Typography>
            </Grid>
            <Grid item>
              <NotSupportedOnMobileText textAlign="center">
                Thanks for trying out GraphMyRepo.com! The site currently only
                works on screens with resolution of at least 900x600. Please
                visit us again from a desktop browser!
              </NotSupportedOnMobileText>
            </Grid>
          </Grid>
        </MobileMessageContainer>
        <Grid item xs={12}>
          <Footer showPantsInfo={isMobile} />
        </Grid>
      </GridTopElement>
      <StyledSnackbar
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        autoHideDuration={5000}
        open={open}
        onClose={() => setOpen(false)}
        message={
          <Typography variant="body2" color="white">
            Link copied. We invite you to share it on Twitter, LinkedIn, Reddit,
            Facebook, and more!
          </Typography>
        }
        action={
          <IconButton
            size="small"
            aria-label="close"
            color="inherit"
            onClick={() => setOpen(false)}
          >
            <StyledCloseIcon color="inherit" />
          </IconButton>
        }
      />
    </Background>
  );
}

export default Results;
