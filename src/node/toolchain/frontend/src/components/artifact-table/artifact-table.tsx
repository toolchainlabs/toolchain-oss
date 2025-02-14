/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import MUIDataTable, { MUIDataTableProps } from 'mui-datatables';
import Typography from '@mui/material/Typography';

import { MetricsContent, Artifact } from 'common/interfaces/build-artifacts';
import ArtifactCard from 'pages/builds/artifact-card';

type ArtifactTableProps = {
  artifact: Artifact<MetricsContent>;
  artifactDescription?: string;
};

const formatMetricCounterName = (name: string) => {
  const capitalized = name && name.length && name.charAt(0).toUpperCase() + name.slice(1);
  return capitalized.replace(/_/g, ' ');
};

const ArtifactTable = ({ artifact, artifactDescription }: ArtifactTableProps) => {
  const columns = [
    {
      name: 'counter',
      label: 'COUNTER',
      options: {
        customHeadLabelRender: () => (
          <Typography variant="overline" color="text.secondary">
            COUNTER
          </Typography>
        ),
      },
    },
    {
      name: 'value',
      label: 'VALUE',
      options: {
        customHeadLabelRender: () => (
          <Typography variant="overline" color="text.secondary">
            VALUE
          </Typography>
        ),
      },
    },
  ];
  const options: Partial<MUIDataTableProps['options']> = {
    filter: false,
    pagination: false,
    selectableRowsHeader: false,
    selectableRows: 'none',
    responsive: 'standard',
    print: false,
    download: false,
    search: false,
    viewColumns: false,
    elevation: 0,
    tableId: '0',
  };
  const data = Object.keys(artifact.content).map(key => [
    formatMetricCounterName(key),
    artifact.content[key].toLocaleString(undefined, { maximumFractionDigits: 2 }),
  ]);

  return (
    <ArtifactCard description={artifactDescription}>
      <MUIDataTable columns={columns} data={data} title="" options={options} />
    </ArtifactCard>
  );
};

export default ArtifactTable;
