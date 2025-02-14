/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { fireEvent, screen } from '@testing-library/react';
import { Routes, Route } from 'react-router-dom';
import { Artifact, PytestResults, TestsAndOutputsContent } from 'common/interfaces/build-artifacts';
import TestOutcomeType from 'common/enums/TestOutcomeType';
import { testOutcomeText } from 'components/icons/test-outcome';
import TestResultsWithStdout, { getAllTests, hasAnyFailed } from './test-results-table-with-stdout';
import {
  testResultsV2,
  testResultsV2TestNames,
  mixedTestResultsTwo,
} from '../../../../tests/__fixtures__/artifacts/test-results';
import render from '../../../../tests/custom-render';

const pytestResultArtifact: Artifact<PytestResults> = testResultsV2;

const getTestResult = (index: number): TestsAndOutputsContent => {
  return pytestResultArtifact.content.test_runs[index];
};
const getPytestResultArtifact = (index: number): Artifact<PytestResults> => {
  return {
    ...pytestResultArtifact,
    content: {
      test_runs: [getTestResult(index)],
    },
  };
};

const writeTextMock = jest.fn();

// Declare the writeText method since in jsdom its undefined (https://stackoverflow.com/a/62356286/14436058)
Object.assign(navigator, {
  clipboard: {
    writeText: () => {},
  },
});
jest.spyOn(navigator.clipboard, 'writeText').mockImplementation(writeTextMock);

const contentWithMixedOutcome: TestsAndOutputsContent = getTestResult(0);
const contentWithOneOutcomeAndOneTest: TestsAndOutputsContent = getTestResult(1);
const contentWithOneOutcome: TestsAndOutputsContent = getTestResult(2);

const artifactWithMixedContentOutcome: Artifact<PytestResults> = getPytestResultArtifact(0);
const artifactWithMixedContentOutcomeAndOneTest: Artifact<PytestResults> = getPytestResultArtifact(1);
const artifactWithOneOutcomeContent: Artifact<PytestResults> = getPytestResultArtifact(2);

const renderTestResultsTableWithStdout = ({
  artifact = artifactWithMixedContentOutcome,
}: Partial<React.ComponentProps<typeof TestResultsWithStdout>> = {}) =>
  render(
    <Routes>
      <Route path="/" element={<TestResultsWithStdout artifact={artifact} />} />
    </Routes>,
    { wrapperProps: { pathname: '/' } }
  );

describe('<TestResultsWithStdout />', () => {
  it('should render component', () => {
    const { asFragment } = renderTestResultsTableWithStdout();

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render table headers', () => {
    renderTestResultsTableWithStdout();

    expect(screen.getByText(/test name/i)).toBeInTheDocument();
    expect(screen.getByText(/outcome/i)).toBeInTheDocument();
    expect(screen.getByText(/duration/i)).toBeInTheDocument();
  });

  it('should render artifact data in table', () => {
    renderTestResultsTableWithStdout();

    contentWithMixedOutcome.tests.forEach(testFile =>
      testFile.tests.forEach(({ name, time, outcome }) => {
        expect(screen.getByText(`${testFile.name}/${name}`)).toBeInTheDocument();
        expect(screen.getByText(`${time}s`)).toBeInTheDocument();
        // If outcome is valid
        if (testOutcomeText[outcome]) {
          expect(screen.getByText(testOutcomeText[outcome])).toBeInTheDocument();
        }
      })
    );
  });

  it('should render row for data with unknown outcome successfully data in table', () => {
    renderTestResultsTableWithStdout();

    contentWithMixedOutcome.tests.forEach(testFile => {
      const { name, time } = testFile.tests.find(({ outcome }) => !Object.values(TestOutcomeType).includes(outcome));

      expect(screen.getByText(`${testFile.name}/${name}`)).toBeInTheDocument();
      expect(screen.getByText(`${time}s`)).toBeInTheDocument();
    });
  });

  it('should render results with only message', () => {
    renderTestResultsTableWithStdout();

    contentWithMixedOutcome.tests.forEach(testFile => {
      const { results } = testFile.tests.find(({ results: res }) => res && res[0].message);

      expect(screen.getByText(results[0].message)).toBeInTheDocument();
    });
  });

  it('should render results with message and text', () => {
    renderTestResultsTableWithStdout();

    contentWithMixedOutcome.tests.forEach(testFile => {
      const { results } = testFile.tests.find(
        ({ results: res }) => res && res[0].message && res[0].text && res[0].text.length < 300
      );

      expect(screen.getByText(results[0].message)).toBeInTheDocument();
      expect(screen.getByText(results[0].text)).toBeInTheDocument();
    });
  });

  it('should render text and message for larger message and/or text', () => {
    renderTestResultsTableWithStdout();

    contentWithMixedOutcome.tests.forEach(testFile => {
      const { results } = testFile.tests.find(
        ({ results: res }) => res && res[0].message && res[0].text && res[0].text.length > 300
      );

      expect(screen.getByText(results[0].message)).toBeInTheDocument();
      expect(screen.getByText(results[0].text)).toBeInTheDocument();
    });
  });

  it('should render correct footer text for multiple outcomes and tests', () => {
    renderTestResultsTableWithStdout();

    // Dont filter out passed tests as we use these in the counter
    const testsOutcomes = contentWithMixedOutcome.tests.reduce(
      (acc, testFile) => [
        ...acc,
        ...testFile.tests.map(({ outcome }) => testOutcomeText[outcome]).filter(outcome => outcome),
      ],
      []
    );
    testsOutcomes.forEach(outcome => {
      const count = testsOutcomes.filter(out => out === outcome).length;

      expect(screen.getByText(`${count} ${outcome}`)).toBeInTheDocument();
    });

    expect(screen.getByText('and')).toBeInTheDocument();
    expect(screen.getByText('tests')).toBeInTheDocument();
    expect(screen.queryByText('test')).not.toBeInTheDocument();
  });

  it('should render correct footer text for one outcome and one test', () => {
    renderTestResultsTableWithStdout({ artifact: artifactWithMixedContentOutcomeAndOneTest });

    // Dont filter out passed tests as we use these in the counter
    const testsOutcomes = contentWithOneOutcomeAndOneTest.tests.reduce(
      (acc, testFile) => [
        ...acc,
        ...testFile.tests.map(({ outcome }) => testOutcomeText[outcome]).filter(outcome => outcome),
      ],
      []
    );

    fireEvent.click(screen.queryByText('second/target'));

    testsOutcomes.forEach(outcome => {
      const count = testsOutcomes.filter(out => out === outcome).length;

      expect(screen.getByText(`${count} ${outcome}`)).toBeInTheDocument();
    });

    expect(screen.queryByText('and')).not.toBeInTheDocument();
    expect(screen.queryByText('tests')).not.toBeInTheDocument();
    expect(screen.getByText('test')).toBeInTheDocument();
  });

  it('should not render table if not expanded', () => {
    renderTestResultsTableWithStdout({ artifact: artifactWithMixedContentOutcomeAndOneTest });

    expect(screen.queryByLabelText('Collapse text')).not.toBeInTheDocument();
  });

  it('should render correct footer text for one outcome but multiple tests', () => {
    renderTestResultsTableWithStdout({ artifact: artifactWithOneOutcomeContent });

    // Dont filter out passed tests as we use these in the counter
    const testsOutcomes = contentWithOneOutcome.tests.reduce(
      (acc, testFile) => [
        ...acc,
        ...testFile.tests.map(({ outcome }) => testOutcomeText[outcome]).filter(outcome => outcome),
      ],
      []
    );

    testsOutcomes.forEach(outcome => {
      const count = testsOutcomes.filter(out => out === outcome).length;

      expect(screen.getByText(`${count} ${outcome}`)).toBeInTheDocument();
    });
    expect(screen.queryByText('and')).not.toBeInTheDocument();
    expect(screen.getByText('tests')).toBeInTheDocument();
    expect(screen.queryByText('test')).not.toBeInTheDocument();
  });

  it('should render output for test results', () => {
    renderTestResultsTableWithStdout({ artifact: artifactWithOneOutcomeContent });

    expect(screen.getByText(contentWithOneOutcome.outputs.stdout)).toBeInTheDocument();
  });

  it('should render total duration for test results', () => {
    renderTestResultsTableWithStdout();

    contentWithMixedOutcome.tests.forEach(testFile =>
      expect(screen.getByText(`${testFile.time.toFixed(2)}s`)).toBeInTheDocument()
    );
  });

  it('should render failed test results expanded and should collapse on click', () => {
    renderTestResultsTableWithStdout();

    expect(screen.getByLabelText('Collapse text')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('Collapse text'));

    expect(screen.queryByLabelText('Collapse text')).not.toBeInTheDocument();
  });

  it('should render passed test results collapsed and should expand on click', () => {
    renderTestResultsTableWithStdout({ artifact: artifactWithMixedContentOutcomeAndOneTest });

    expect(screen.queryByLabelText('Collapse text')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTitle('SUCCESS'));

    expect(screen.getByLabelText('Collapse text')).toBeInTheDocument();
  });

  it('should render failed first as default sort', () => {
    renderTestResultsTableWithStdout({ artifact: pytestResultArtifact });

    expect(screen.getByText('SORT: FAILED FIRST')).toBeInTheDocument();
  });

  it('should sort on click', () => {
    renderTestResultsTableWithStdout({ artifact: pytestResultArtifact });

    // create list of timings before sort
    const defaultOrder = screen.queryAllByTestId('timing');

    fireEvent.click(screen.getByText('SORT: FAILED FIRST'));
    // create list of timings after sort
    const orderAfterSort = screen.queryAllByTestId('timing');

    expect(screen.getByText('SORT: RUNTIME DESC')).toBeInTheDocument();
    // compare orders
    expect(orderAfterSort).not.toBe(defaultOrder);
  });

  it('should render tests names with target name prefixed (separated by /)', () => {
    renderTestResultsTableWithStdout({ artifact: testResultsV2TestNames });

    const targetName = testResultsV2TestNames.content.test_runs[0].target;
    const testFileName = testResultsV2TestNames.content.test_runs[0].tests[0].name;
    const testWithStartingLetter = testResultsV2TestNames.content.test_runs[0].tests[0].tests[0].name;
    const testWithStartingNumber = testResultsV2TestNames.content.test_runs[0].tests[0].tests[1].name;
    const testsWithStartingOther = testResultsV2TestNames.content.test_runs[0].tests[0].tests[2].name;

    expect(screen.getByText(targetName)).toBeInTheDocument();

    fireEvent.click(screen.getByText(targetName));

    expect(screen.getByText(`${testFileName}/${testWithStartingLetter}`)).toBeInTheDocument();
    expect(screen.getByText(`${testFileName}/${testWithStartingNumber}`)).toBeInTheDocument();
    expect(screen.getByText(testsWithStartingOther)).toBeInTheDocument();
  });

  it('should render total number of targets', () => {
    renderTestResultsTableWithStdout({ artifact: pytestResultArtifact });

    expect(screen.getByText('Total: 3 Targets')).toBeInTheDocument();
  });

  it('should render one filtered target message', () => {
    renderTestResultsTableWithStdout({ artifact: pytestResultArtifact });

    const seachBox = screen.getByLabelText('Search file');

    fireEvent.change(seachBox, { target: { value: 'first' } });

    expect(screen.getByText('Search result: 1 Target')).toBeInTheDocument();
  });

  it('should render multiple filtered targets message', () => {
    renderTestResultsTableWithStdout({ artifact: pytestResultArtifact });

    const seachBox = screen.getByLabelText('Search file');

    fireEvent.change(seachBox, { target: { value: 'i' } });

    expect(screen.getByText('Search result: 2 Targets')).toBeInTheDocument();
  });

  it('should display only filtered results after re-sorting them', () => {
    renderTestResultsTableWithStdout({ artifact: pytestResultArtifact });

    const seachBox = screen.getByLabelText('Search file');

    fireEvent.change(seachBox, { target: { value: 'i' } });

    const sortButton = screen.getByRole('button', {
      name: /SORT/i,
    });

    fireEvent.click(sortButton);

    expect(screen.getByText('Search result: 2 Targets')).toBeInTheDocument();
  });

  it('should make linear array of all tests results', () => {
    const testContent = mixedTestResultsTwo.content.test_runs[0].tests;
    const testsResultsAray = getAllTests(testContent);

    expect(testsResultsAray).toHaveLength(11);
  });

  it('should check if any of tests failed', () => {
    const allPassedResults = [TestOutcomeType.PASSED, TestOutcomeType.PASSED, TestOutcomeType.PASSED];

    const oneErrorResult = [...allPassedResults, TestOutcomeType.ERROR];
    const oneFailedResult = [...allPassedResults, TestOutcomeType.FAILED];
    const oneXFailedResult = [...allPassedResults, TestOutcomeType.X_FAILED];

    expect(hasAnyFailed(allPassedResults)).toBeFalsy();
    expect(hasAnyFailed(oneErrorResult)).toBeTruthy();
    expect(hasAnyFailed(oneFailedResult)).toBeTruthy();
    expect(hasAnyFailed(oneXFailedResult)).toBeTruthy();
  });

  it('should copy direct link to clipboard', () => {
    renderTestResultsTableWithStdout({ artifact: pytestResultArtifact });

    const currentUrl = window.location.href;
    const expectedUrl = currentUrl + '#' + pytestResultArtifact.content.test_runs[0].target;

    fireEvent.click(screen.queryAllByLabelText('Copy direct link')[0]);

    expect(writeTextMock).toHaveBeenCalledWith(expectedUrl);
  });

  it('should display snackbar message on direct link button click', () => {
    renderTestResultsTableWithStdout({ artifact: pytestResultArtifact });

    fireEvent.click(screen.queryAllByLabelText('Copy direct link')[0]);

    expect(screen.getByText('Direct link copied')).toBeInTheDocument();
  });
});
