/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen } from '@testing-library/react';

import ArtifactTable from './artifact-table';
import { workUnitMetrics } from '../../../tests/__fixtures__/artifacts/metrics';
import render from '../../../tests/custom-render';

const renderArtifactTable = ({
  artifact = workUnitMetrics,
}: Partial<React.ComponentProps<typeof ArtifactTable>> = {}) => render(<ArtifactTable artifact={artifact} />);

describe('<ArtifactTable />', () => {
  it('should render the component', () => {
    const { asFragment } = renderArtifactTable();

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render counter and value header and column identifiers', () => {
    renderArtifactTable();

    expect(screen.getAllByText('VALUE')).not.toBeNull();
    expect(screen.getAllByText('COUNTER')).not.toBeNull();
  });

  it('should render counter value capitalized and with space instead of underscore', () => {
    renderArtifactTable();

    expect(screen.getByText('Some metric one')).toBeInTheDocument();
    expect(screen.getByText('Some metric two')).toBeInTheDocument();
    expect(screen.getByText('Some metric three')).toBeInTheDocument();
    expect(screen.getByText('Some metric four')).toBeInTheDocument();
  });

  it('should render two sort columns', () => {
    renderArtifactTable();

    expect(screen.getAllByLabelText('Sort')).toHaveLength(2);
  });

  it(`should render locale string value`, () => {
    const number = 3500.2;
    const numberTwo = 35000.2;
    const numberThree = 350000.2;
    renderArtifactTable({
      artifact: {
        ...workUnitMetrics,
        content: { firstMetric: number, secondMetric: numberTwo, thirdMetric: numberThree },
      },
    });

    expect(screen.getByText('3,500.2')).toBeInTheDocument();
    expect(screen.getByText('35,000.2')).toBeInTheDocument();
    expect(screen.getByText('350,000.2')).toBeInTheDocument();
  });
});
