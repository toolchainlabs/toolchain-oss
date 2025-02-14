/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { Fragment, useState, useCallback, useEffect, useRef } from 'react';
import Typography from '@mui/material/Typography';
import MuiTable from '@mui/material/Table';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import TableCell from '@mui/material/TableCell';
import TableBody from '@mui/material/TableBody';
import TableFooter from '@mui/material/TableFooter';
import Grid from '@mui/material/Grid';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import Box from '@mui/material/Box';
import FormControl from '@mui/material/FormControl';
import TextField from '@mui/material/TextField';
import Collapse from '@mui/material/Collapse';
import Button from '@mui/material/Button';
import Sort from '@mui/icons-material/Sort';
import { useLocation } from 'react-router-dom';
import CloseIcon from '@mui/icons-material/Close';
import Snackbar from '@mui/material/Snackbar';
import IconButton from '@mui/material/IconButton';

import {
  Artifact,
  TestContent,
  TestOutput,
  TestResult as ResultType,
  TestsAndOutputsContent,
  PytestResults,
} from 'common/interfaces/build-artifacts';
import TestOutcome, { testOutcomeText } from 'components/icons/test-outcome';
import TextBlockWithScroll from 'components/text-block-with-scroll/text-block-with-scroll';
import TestOutcomeType from 'common/enums/TestOutcomeType';
import ArtifactCard from 'pages/builds/artifact-card';
import OutcomeType from 'common/enums/OutcomeType';
import { convertTestOutcomeToTargetOutcome } from '../../../utils/test-outcome-converter';
import { styled } from '@mui/material/styles';
import { List, ListRowRenderer, WindowScroller } from 'react-virtualized';
import useWindowSize from '../../../utils/hooks/useWindowSize';
import { default as muiTheme } from 'utils/theme';

type OutcomeObject = { outcome: string; count: number; value: string };
type FooterTypographyProps = OutcomeObject & { index: number; outcomes: OutcomeObject[] };
type TargetCardProps = {
  tests: TestContent[];
  outputs: TestOutput;
  target: string;
  targetIndex: number;
  setRefHeight: (index: number, value: number) => void;
  targetsStateRef: {
    current?: TargetsStateType;
  };
  setMyRenderingIndex: () => void;
  unsetMyRenderingIndex: () => void;
  openSnackbar: () => void;
};
type TestResultsTableProps = { testFile: TestContent; outputs: TestOutput };
type TestResulsSearchAndFilterProps = {
  setSort: React.Dispatch<React.SetStateAction<string>>;
  setFilterValue: React.Dispatch<React.SetStateAction<string>>;
  setIsUpdatingSort: React.Dispatch<React.SetStateAction<boolean>>;
  isUpdatingSort: boolean;
  sort: string;
  numberOfShownResults: number;
  filterValue: string;
};
type TargetsStateType = Map<string, boolean | undefined>;
type RowInfoType = { index: number };

type LoadingIndicatorType = { height: number };

type LoadingElementType = {
  width: number;
  height: number;
  borderRadius: number;
  backgroundColor: string;
};

const SORT: { [key: string]: string } = {
  FAILED_FIRST: 'FAILED FIRST',
  RUN_TIME_DESC: 'RUNTIME DESC',
};

const DEFAULT_ROW_HEIGHT = 80;
const ROW_PADDING_SIZE = 24;
const PAGE_PADDING = 174;
const LARGE_NUMBER_OF_TESTS = 10;
const INITIAL_SCROLL_DELAY = 200; // in ms - should be longer than rows heigh calculation time

export const getAllTests = (tests: TestContent[]) => {
  const allTestsResults: Array<TestOutcomeType> = [];

  tests.forEach(testFile => {
    testFile.tests.forEach(test => {
      allTestsResults.push(test.outcome);
    });
  });

  return allTestsResults;
};

export const hasAnyFailed = (allTestsResults: TestOutcomeType[]) => {
  const hasFailed = allTestsResults.some(outcome => {
    return (
      outcome === TestOutcomeType.ERROR || outcome === TestOutcomeType.FAILED || outcome === TestOutcomeType.X_FAILED
    );
  });

  return hasFailed;
};

const StyledTableRow = styled(TableRow)(({ theme }) => ({
  [`& td`]: {
    lineBreak: 'anywhere',
    padding: `12px ${theme.spacing(2)}`,
    [`&:first-of-type`]: {
      width: '75.69%;',
    },
    [`&:nth-of-type(2)`]: {
      width: '13.88%;',
    },
    [`&:nth-of-type(3)`]: {
      width: '10.41%;',
    },
  },
}));

const FooterGrid = styled(TableCell)(({ theme }) => ({
  padding: `6px ${theme.spacing(2)}`,
  border: 0,
}));

const SortBox = styled(Box)(({ theme }) => ({
  backgroundColor: theme.palette.common.white,
  borderRadius: theme.spacing(1),
  padding: theme.spacing(1),
  marginBottom: theme.spacing(1),
  minHeight: 64,
  display: 'flex',
}));

const SortIcon = styled(Sort)(() => ({
  width: 18,
  heigth: 12,
}));

const SearchBox = styled(Box)(({ theme }) => ({
  backgroundColor: theme.palette.common.white,
  borderRadius: theme.spacing(1),
  padding: `${theme.spacing(1)} ${theme.spacing(3)}`,
  marginBottom: theme.spacing(1),
}));

const FullHeight = styled(Grid)(() => ({
  height: '100%',
}));

const ExpandButton = styled(Button)(({ theme }) => ({
  width: 162,
  height: 32,
  borderRadius: `${theme.spacing(2)} ${theme.spacing(2)} 0 0`,
  backgroundColor: 'rgba(0, 169, 183, 0.08)',
  textAlign: 'center',
  position: 'relative',
  top: theme.spacing(3),
  [`&:hover`]: {
    backgroundColor: theme.palette.primary.main,
    [`&  svg`]: {
      transition: 'color 250ms',
      color: theme.palette.common.white,
    },
  },
}));

const FooterInfoMarginRight = styled(Typography)(() => ({
  marginRight: 5,
}));

const FooterInfoMarginLeft = styled(Typography)(() => ({
  marginLeft: 5,
}));

const CollapseWrapper = styled(Box)(({ theme }) => ({
  cursor: 'pointer',
  marginBottom: theme.spacing(3),
  borderRadius: theme.spacing(1),
  border: `1px solid transparent`,
  [`&:hover`]: {
    borderColor: theme.palette.primary.main,
  },
}));

const StyledTextField = styled(TextField)(() => ({
  width: '100%',
  '&:after': {
    display: 'none',
  },
}));

const StyledCollapse = styled(Collapse)(({ theme }) => ({
  '& .MuiCollapse-wrapper': {
    position: 'relative',
    borderRadius: theme.spacing(1),
  },
  '&.MuiCollapse-root': {
    borderRadius: theme.spacing(1),
  },
}));

const LoadingContainer = styled(Grid)<LoadingIndicatorType>(({ height }) => ({
  width: '100%',
  height: height,
  padding: '32px 24px',
  backgroundColor: '#fff',
  borderRadius: 8,
  position: 'relative',
}));

const LoadingElement = styled(Grid)<LoadingElementType>(({ width, backgroundColor, borderRadius, height }) => ({
  width: width,
  height: height,
  backgroundColor: backgroundColor,
  borderRadius: borderRadius,
}));

const BigLoadingElement = styled(Grid)(({ theme }) => ({
  height: '100%',
  flex: 1,
  backgroundColor: '#E0E0E0',
  marginRight: theme.spacing(2),
}));

const LoadingText = styled(Typography)(() => ({
  position: 'absolute',
  top: '50%',
  left: '50%',
  transform: 'translateX(-50%) translateY(-50%)',
  zIndex: 1,
}));

const CountBox = styled(Box)(({ theme }) => ({
  backgroundColor: theme.palette.common.white,
  borderRadius: theme.spacing(1),
  padding: `${theme.spacing(2.5)} ${theme.spacing(2)}`,
  marginBottom: theme.spacing(1),
}));

const LoadingIndicator = ({ height }: LoadingIndicatorType) => {
  return (
    <LoadingContainer container alignItems="flex-start" height={height}>
      <LoadingText variant="body2">Loading...</LoadingText>
      <LoadingElement
        item
        height={20}
        width={20}
        backgroundColor={muiTheme.palette.grey[500]}
        marginRight={1}
        borderRadius={20}
        marginTop={-0.25}
      />
      <LoadingElement
        item
        height={16}
        width={40}
        backgroundColor={muiTheme.palette.grey[500]}
        marginRight={3}
        borderRadius={0}
      />
      <LoadingElement
        item
        height={16}
        width={64}
        backgroundColor={muiTheme.palette.grey[500]}
        marginRight={1}
        borderRadius={0}
      />

      <BigLoadingElement item />
      <LoadingElement
        item
        height={16}
        width={40}
        backgroundColor={'rgba(0, 169, 183, 0.5)'}
        marginRight={1}
        borderRadius={0}
      />
    </LoadingContainer>
  );
};

const Output = ({ text }: { text: string }) => (
  <Box marginTop={2} marginBottom={2}>
    <TextBlockWithScroll size="large" color="blue">
      {text}
    </TextBlockWithScroll>
  </Box>
);

const Result = ({ text, message }: ResultType) => {
  return (
    <StyledTableRow>
      <TableCell component="td" scope="row" colSpan={3}>
        <TextBlockWithScroll size="small" color="gray">
          <Grid container spacing={1}>
            <Grid item>
              <Typography variant="subtitle2">{message}</Typography>
            </Grid>
            {text && (
              <Grid item>
                <Typography variant="body2">{text}</Typography>
              </Grid>
            )}
          </Grid>
        </TextBlockWithScroll>
      </TableCell>
    </StyledTableRow>
  );
};

const FooterTypography = ({ count, outcome, value, index, outcomes }: FooterTypographyProps) => {
  const hasMultipleTests = count > 1;
  const hasValidOutcome = count > 0;
  const hasMultipleOutcomes = outcomes.length > 1;
  const isLastIndex = index === outcomes.length - 1;

  return hasValidOutcome ? (
    <>
      {isLastIndex && hasMultipleOutcomes && <FooterInfoMarginRight variant="body2">and</FooterInfoMarginRight>}
      <Typography variant="body2" className={outcome}>
        {value}
      </Typography>
      {isLastIndex ? (
        <FooterInfoMarginLeft variant="body2">
          {!hasMultipleOutcomes && !hasMultipleTests ? 'test' : 'tests'}
        </FooterInfoMarginLeft>
      ) : (
        <FooterInfoMarginRight variant="body2">,</FooterInfoMarginRight>
      )}
    </>
  ) : null;
};

const TestResultsTable = ({ testFile, outputs }: TestResultsTableProps) => {
  const possibleOutcomes = Object.values(TestOutcomeType);
  const outcomesCount = possibleOutcomes.map(value => testFile.tests.filter(test => test.outcome === value).length);
  const outcomes = outcomesCount
    .map((count, index) => ({
      count,
      outcome: possibleOutcomes[index],
      value: `${count} ${testOutcomeText[possibleOutcomes[index]]}`,
    }))
    .filter(({ count }) => count > 0);

  const isLetter = (string: string) => string.match(/[a-z]/i);
  const isNumber = (string: string) => string.match(/^[0-9]$/i);

  return (
    <>
      <TableContainer>
        <MuiTable aria-label="table" role="grid">
          <TableHead>
            <StyledTableRow>
              <TableCell component="td" scope="row">
                <Typography variant="overline" color="textSecondary">
                  TEST NAME
                </Typography>
              </TableCell>
              <TableCell component="td" scope="row">
                <Typography variant="overline" color="textSecondary">
                  OUTCOME
                </Typography>
              </TableCell>
              <TableCell component="td" scope="row">
                <Typography variant="overline" color="textSecondary">
                  DURATION
                </Typography>
              </TableCell>
            </StyledTableRow>
          </TableHead>
          <TableBody>
            {testFile.tests.map(({ name, time, outcome, results }) => {
              const testName = isNumber(name[0]) || isLetter(name[0]) ? `${testFile.name}/${name}` : name;
              return (
                <Fragment key={name}>
                  <StyledTableRow>
                    <TableCell component="td" scope="row">
                      {testName}
                    </TableCell>
                    <TableCell component="td" scope="row">
                      <TestOutcome outcome={outcome} />
                    </TableCell>
                    <TableCell component="td" scope="row">
                      {time}s
                    </TableCell>
                  </StyledTableRow>
                  {results?.map(({ text, message }) => (
                    <Result key={`${text}-${message}`} text={text} message={message} />
                  ))}
                </Fragment>
              );
            })}
          </TableBody>
          <TableFooter>
            <TableRow>
              <FooterGrid component="td" scope="row" colSpan={3}>
                <Grid container>
                  {outcomes.map(({ count, outcome, value }, index) => (
                    <FooterTypography
                      key={value}
                      count={count}
                      outcome={outcome}
                      value={value}
                      index={index}
                      outcomes={outcomes}
                    />
                  ))}
                </Grid>
              </FooterGrid>
            </TableRow>
          </TableFooter>
        </MuiTable>
      </TableContainer>
      <Output text={outputs.stdout} />
    </>
  );
};

const TargetCard = ({
  tests,
  outputs,
  target,
  targetIndex,
  setRefHeight,
  targetsStateRef,
  setMyRenderingIndex,
  unsetMyRenderingIndex,
  openSnackbar,
}: TargetCardProps) => {
  const [height, setHeight] = useState(800);
  const closedCardRef = useRef(null);
  const { pathname, search } = useLocation();

  const allTestsResults = getAllTests(tests);

  const hasFailed = hasAnyFailed(allTestsResults);

  const firstTestResult = allTestsResults[0] || TestOutcomeType.PASSED;

  const isMixed = !hasFailed && !allTestsResults.every(result => result === firstTestResult);

  let targetOutcome;

  if (hasFailed) {
    targetOutcome = OutcomeType.FAILURE;
  } else if (isMixed) {
    targetOutcome = OutcomeType.MIXED;
  } else {
    targetOutcome = convertTestOutcomeToTargetOutcome(firstTestResult);
  }

  const myRefStateNew = targetsStateRef.current.get(target);
  const isNotSuccessful = targetOutcome !== OutcomeType.SUCCESS;
  const initExpandedState = myRefStateNew !== undefined ? myRefStateNew : isNotSuccessful;

  const [expanded, setExpanded] = useState(initExpandedState);
  const CollapseWrapperComponent = !expanded ? CollapseWrapper : Box;
  const totalDuration = `${tests.reduce((acc, testFile) => acc + testFile.time, 0).toFixed(2)}s`;

  const hasManyTests = tests.length > LARGE_NUMBER_OF_TESTS;

  useEffect(() => {
    const myHeight = closedCardRef.current?.clientHeight;
    setHeight(myHeight);
    setRefHeight(targetIndex, myHeight);
    unsetMyRenderingIndex();
  }, [expanded, setHeight, setRefHeight, targetIndex, unsetMyRenderingIndex]);

  useEffect(() => {
    const prevState = targetsStateRef.current.get(target);
    if (prevState === undefined) {
      targetsStateRef.current.set(target, expanded);
    } else {
      setExpanded(prevState);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target]);

  const setExpandedFlag = () => {
    if (!expanded) {
      if (hasManyTests) {
        setMyRenderingIndex();
      }
      setExpanded(true);
      targetsStateRef.current.set(target, true);
    }
  };

  const unsetExpandedFlag = () => {
    if (expanded) {
      setExpanded(false);
      targetsStateRef.current.set(target, false);
    }
  };

  const onDirectLinkClick = (event: React.MouseEvent<HTMLElement>) => {
    event.stopPropagation();
    const origin = window.location.origin;
    const directLinkUrl = `${origin}${pathname}${search}#${target}`;
    navigator.clipboard.writeText(directLinkUrl);
    openSnackbar();
  };

  return (
    <CollapseWrapperComponent onClick={setExpandedFlag}>
      <StyledCollapse in={expanded} collapsedSize={height} component="div" timeout="auto">
        <ArtifactCard
          ref={closedCardRef}
          hideBody={!expanded}
          description={target}
          outcome={targetOutcome}
          showOutcome
          duration={totalDuration}
          hasDirectLinkButton
          onDirectLinkButtonClick={onDirectLinkClick}
        >
          <>
            {tests.map(testFile => (
              <TestResultsTable
                key={`${testFile.test_file_path}/${testFile.name}`}
                testFile={testFile}
                outputs={outputs}
              />
            ))}
            <Grid container justifyContent="center" alignItems="center">
              <FullHeight container justifyContent="center" alignItems="center">
                <ExpandButton onClick={unsetExpandedFlag} aria-label="Collapse text">
                  <KeyboardArrowUpIcon color="primary" />
                </ExpandButton>
              </FullHeight>
            </Grid>
          </>
        </ArtifactCard>
      </StyledCollapse>
    </CollapseWrapperComponent>
  );
};

const TestResultsSearchAndFilter = ({
  sort,
  setSort,
  setFilterValue,
  isUpdatingSort,
  setIsUpdatingSort,
  numberOfShownResults,
  filterValue,
}: TestResulsSearchAndFilterProps) => {
  const isNotOneTarget = numberOfShownResults !== 1;

  const labelMessage = !!filterValue
    ? `Search result: ${numberOfShownResults} Target${isNotOneTarget ? 's' : ''}`
    : `Total: ${numberOfShownResults} Target${isNotOneTarget ? 's' : ''}`;

  return (
    <Grid container spacing={1}>
      <Grid item xs>
        <SearchBox>
          <FormControl fullWidth>
            <StyledTextField
              label="Search file"
              id="search-file"
              onChange={e => setFilterValue(e.target.value)}
              error={false}
            />
          </FormControl>
        </SearchBox>
      </Grid>
      <Grid item xs="auto">
        <CountBox>
          <Grid container alignItems="center">
            <Grid item>
              <Typography variant="body1" color="textSecondary">
                {labelMessage}
              </Typography>
            </Grid>
          </Grid>
        </CountBox>
      </Grid>
      <Grid item xs="auto">
        <SortBox>
          <Grid container justifyContent="center" alignItems="center">
            <Grid item>
              <Button
                variant="text"
                color="primary"
                startIcon={<SortIcon />}
                onClick={() => {
                  setIsUpdatingSort(true);
                  setSort(SORT[Object.keys(SORT).find(key => SORT[key] !== sort)]);
                }}
                disabled={isUpdatingSort}
              >
                <Typography variant="button3">SORT: {sort}</Typography>
              </Button>
            </Grid>
          </Grid>
        </SortBox>
      </Grid>
    </Grid>
  );
};

const TestResultsWithStdout = ({ artifact }: { artifact: Artifact<PytestResults> }) => {
  const [results, setResults] = useState<TestsAndOutputsContent[]>(artifact.content.test_runs);
  const [sort, setSort] = useState(SORT[Object.keys(SORT)[0]]);
  const [filterValue, setFilterValue] = useState<string>('');
  const [isUpdatingSort, setIsUpdatingSort] = useState(false);
  const [renderingIndex, setRenderingIndex] = useState<number | undefined>();
  const [isSnackBarOpen, setIsSnackBarOpen] = useState<boolean>(false);

  const { windowWidth } = useWindowSize();

  const rowHeightsRef = useRef<Array<number>>([]);
  const targetsStateRef = useRef<TargetsStateType>(new Map());

  const [initialIndex, setInitialIndex] = useState<number>();
  const { hash } = useLocation();

  const clearInitialIndex = () => {
    setInitialIndex(-1);
  };

  useEffect(() => {
    const testRuns = artifact.content.test_runs;
    const trimmedHash = hash?.length > 1 ? hash.substring(1) : '';
    const requiredIndex = testRuns.findIndex(el => el.target === trimmedHash);
    if (requiredIndex >= 0) {
      setTimeout(() => {
        setInitialIndex(requiredIndex);
      }, INITIAL_SCROLL_DELAY);
    }
  }, [hash, artifact.content.test_runs]);

  const listRef = useRef<{
    recomputeRowHeights?: () => void;
  }>();

  const sortTestResults = useCallback((r: TestsAndOutputsContent[], s: string) => {
    const sortedResults = [...r];

    switch (s) {
      case SORT.RUN_TIME_DESC:
        setIsUpdatingSort(false);
        return sortedResults.sort((a, b) => (a.timing.total < b.timing.total ? 1 : -1));
      default:
        setIsUpdatingSort(false);
        return sortedResults;
    }
  }, []);

  useEffect(() => {
    setResults(sortTestResults(artifact.content.test_runs, sort));
  }, [sort, setResults, sortTestResults, artifact.content.test_runs]);

  const setMyHeight = (index: number, myHeight: number) => {
    rowHeightsRef.current[index] = myHeight;
    listRef.current?.recomputeRowHeights();
  };

  const listWidth = windowWidth - PAGE_PADDING;

  const setMyRenderingIndex = (index: number) => setRenderingIndex(index);
  const unsetMyRenderingIndex = () => setRenderingIndex(undefined);

  const doesMatchFilter = (result: TestsAndOutputsContent) => {
    const lowercaseTarget = result.target.toLowerCase();
    const lowercaseFilterValue = filterValue.toLowerCase();

    return lowercaseTarget.includes(lowercaseFilterValue);
  };

  const elements = results
    .filter(result => doesMatchFilter(result))
    .map(({ outputs, tests, target }, index) => {
      return (
        <TargetCard
          key={`${target}-${index}`}
          tests={tests}
          outputs={outputs}
          target={target}
          targetIndex={index}
          setRefHeight={setMyHeight}
          targetsStateRef={targetsStateRef}
          setMyRenderingIndex={() => setMyRenderingIndex(index)}
          unsetMyRenderingIndex={unsetMyRenderingIndex}
          openSnackbar={() => setIsSnackBarOpen(true)}
        />
      );
    });

  const rowRenderer: ListRowRenderer = ({ key, index, style }) => {
    const isLoadingElement = renderingIndex === index;
    const myHeight = rowHeightsRef.current[index];

    return (
      <div key={key} style={style}>
        {isLoadingElement && <LoadingIndicator height={myHeight} />}
        <div
          style={{
            opacity: isLoadingElement ? 0 : 1,
          }}
        >
          {elements[index]}
        </div>
      </div>
    );
  };

  const getRowHeight = ({ index }: RowInfoType) => {
    const myHeight = rowHeightsRef.current[index] + ROW_PADDING_SIZE || DEFAULT_ROW_HEIGHT;
    return myHeight;
  };

  const isInitialIndexSet = initialIndex >= 0;

  return (
    <>
      <TestResultsSearchAndFilter
        sort={sort}
        setSort={setSort}
        isUpdatingSort={isUpdatingSort}
        setIsUpdatingSort={setIsUpdatingSort}
        numberOfShownResults={elements.length}
        filterValue={filterValue}
        setFilterValue={setFilterValue}
      />
      <WindowScroller onScroll={clearInitialIndex}>
        {({ height, isScrolling, onChildScroll, scrollTop }) => {
          return (
            <List
              autoHeight
              height={height}
              isScrolling={isScrolling}
              onScroll={onChildScroll}
              ref={listRef as React.Ref<List>}
              width={listWidth}
              scrollTop={!isInitialIndexSet ? scrollTop : undefined}
              rowCount={elements.length}
              rowHeight={getRowHeight}
              rowRenderer={rowRenderer}
              scrollToIndex={initialIndex}
              scrollToAlignment="start"
              overscanRowCount={5}
            />
          );
        }}
      </WindowScroller>
      <Snackbar
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        autoHideDuration={5000}
        open={isSnackBarOpen}
        onClose={() => setIsSnackBarOpen(false)}
        message="Direct link copied"
        action={
          <IconButton size="small" aria-label="close" color="inherit" onClick={() => setIsSnackBarOpen(false)}>
            <CloseIcon />
          </IconButton>
        }
      />
    </>
  );
};

export default TestResultsWithStdout;
