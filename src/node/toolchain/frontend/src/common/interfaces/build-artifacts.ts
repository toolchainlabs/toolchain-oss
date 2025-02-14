/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import TestOutcomeType from 'common/enums/TestOutcomeType';

type TestFailure = {
  message: string;
  text: string;
};

export type TestResult = {
  message: string;
  text?: string;
};

export type TestCase = {
  name: string;
  time: number;
  outcome?: TestOutcomeType;
  failures?: TestFailure[];
  results?: TestResult[];
};

type TargetValue = any;

type PantsOptionsValue = any;

export type MetricsContent = { [key: string]: number };

export type TargetsContent = TargetValue;

export type PantsOptionsContent = PantsOptionsValue;

export type ConsoleContent = string;

export type LogArtifactContent = string;

export type TestContent = {
  name: string;
  test_file_path: string;
  tests: TestCase[];
  time: number;
};

export type TestOutput = {
  stderr: string;
  stdout: string;
};

export type PytestResults = {
  test_runs: TestsAndOutputsContent[];
};

export type TestsAndOutputsContent = {
  outputs: TestOutput;
  tests: TestContent[];
  target: string;
  timing: {
    total: number;
  };
};

export type ArtifactProps<T> = {
  artifact: Artifact<T>;
};

export interface BuildArtifact {
  name: string;
  description: string;
  result?: string;
  group?: string;
  content_types?: string[];
}

type Timing = {
  run_time: number;
  start_time: number;
};

export enum EnvName {
  REMOTE = 'Remote',
  LOCAL = 'Local',
}

export type Artifact<T> = {
  content: T;
  name: string;
  content_type: string;
  env_name?: EnvName | string;
  from_cache?: boolean;
  timing_msec?: Timing;
};

export type ArtifactsResponse<T> = Artifact<T>[];

export type AllArtifactContents =
  | MetricsContent
  | TargetsContent
  | PantsOptionsContent
  | ConsoleContent
  | LogArtifactContent
  | TestsAndOutputsContent;
