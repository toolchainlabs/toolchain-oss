/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen } from '@testing-library/react';

import TestOutcomeType from 'common/enums/TestOutcomeType';
import TestOutcome, { testOutcomeText } from './test-outcome';
import render from '../../../tests/custom-render';

const renderTestOutcome = ({ outcome }: Partial<React.ComponentProps<typeof TestOutcome>> = {}) =>
  render(<TestOutcome outcome={outcome} />);

describe('<TestOutcome />', () => {
  it('should render test outcome PASSED', () => {
    renderTestOutcome({ outcome: TestOutcomeType.PASSED });

    expect(screen.getByText(testOutcomeText[TestOutcomeType.PASSED])).toBeInTheDocument();
  });

  it('should render test outcome FAILED', () => {
    renderTestOutcome({ outcome: TestOutcomeType.FAILED });

    expect(screen.getByText(testOutcomeText[TestOutcomeType.FAILED])).toBeInTheDocument();
  });

  it('should render test outcome ERROR', () => {
    renderTestOutcome({ outcome: TestOutcomeType.ERROR });

    expect(screen.getByText(testOutcomeText[TestOutcomeType.ERROR])).toBeInTheDocument();
  });

  it('should render test outcome SKIPPED', () => {
    renderTestOutcome({ outcome: TestOutcomeType.SKIPPED });

    expect(screen.getByText(testOutcomeText[TestOutcomeType.SKIPPED])).toBeInTheDocument();
  });

  it('should render test outcome X_FAILED', () => {
    renderTestOutcome({ outcome: TestOutcomeType.X_FAILED });

    expect(screen.getByText(testOutcomeText[TestOutcomeType.X_FAILED])).toBeInTheDocument();
  });

  it('should render test outcome X_PASSED', () => {
    renderTestOutcome({ outcome: TestOutcomeType.X_PASSED });

    expect(screen.getByText(testOutcomeText[TestOutcomeType.X_PASSED])).toBeInTheDocument();
  });

  it('should render test outcome X_PASSED_STRICT', () => {
    renderTestOutcome({ outcome: TestOutcomeType.X_PASSED_STRICT });

    expect(screen.getByText(testOutcomeText[TestOutcomeType.X_PASSED_STRICT])).toBeInTheDocument();
  });

  it('should not render random test outcome', () => {
    const { asFragment } = renderTestOutcome({ outcome: 'randomeOutcome' } as any);

    expect(asFragment()).toMatchSnapshot();
  });
});
