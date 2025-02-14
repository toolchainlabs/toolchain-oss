/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen } from '@testing-library/react';

import OutcomeType from 'common/enums/OutcomeType';
import { BuildOutcome } from './build-outcome';
import render from '../../../tests/custom-render';

const renderBuildOutcome = ({
  outcome,
  chipVariant,
  chipSize,
}: Partial<React.ComponentProps<typeof BuildOutcome>> = {}) =>
  render(<BuildOutcome outcome={outcome} chipVariant={chipVariant} chipSize={chipSize} />);

describe('<BuildOutcome />', () => {
  it('should render success outcome', () => {
    const { asFragment } = renderBuildOutcome({ outcome: OutcomeType.SUCCESS });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render failed outcome', () => {
    const { asFragment } = renderBuildOutcome({ outcome: OutcomeType.FAILURE });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render aborted outcome', () => {
    const { asFragment } = renderBuildOutcome({ outcome: OutcomeType.ABORTED });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render running outcome', () => {
    const { asFragment } = renderBuildOutcome({ outcome: OutcomeType.RUNNING });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render not available outcome', () => {
    const { asFragment } = renderBuildOutcome({ outcome: OutcomeType.NOT_AVAILABLE });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render not available outcome with random outcome string', () => {
    renderBuildOutcome({ outcome: 'random' } as any);

    expect(screen.getByText('Not available')).toBeInTheDocument();
  });
});
