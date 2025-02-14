/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { Artifact, MetricsContent } from 'common/interfaces/build-artifacts';

export const workUnitMetrics: Artifact<MetricsContent> = {
  name: 'eight',
  content: {
    some_metric_one: 10,
    some_metric_two: 20,
    some_metric_three: 30,
    some_metric_four: 40,
  },
  content_type: 'work_unit_metrics',
};

export const codeCoverage = {
  name: 'ninth',
  content: { lines_covered: 6979, lines_uncovered: 1364 },
  content_type: 'coverage_summary',
};
