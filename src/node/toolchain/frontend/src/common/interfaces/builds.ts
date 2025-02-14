/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import OutcomeType from 'common/enums/OutcomeType';
import RunType from 'common/enums/RunType';
import { ApiListResponse } from 'common/interfaces/api';
import { Branch, ToolchainUser, Goal } from 'common/interfaces/builds-options';
import { BuildArtifact } from './build-artifacts';

export interface BuildCIInfo {
  username: string;
  run_type: RunType;
  pull_request: number;
  job_name: string;
  build_num: number;
  links: { icon: string; text: string; link: string }[];
}

export interface GoalData {
  artifacts: BuildArtifact[];
  type: string;
  name?: string;
}

export type BuildArtifacts = { [key: string]: GoalData };

export type DownloadLink = {
  link: string;
  name: string;
};

export type Platform = {
  architecture: string;
  cpu_count: number;
  mem_bytes: number;
  os: string;
  os_release: string;
  processor: string;
  python_implementation: string;
  python_version: string;
};
export interface Build {
  branch: Branch;
  datetime: string;
  run_time: number;
  outcome: OutcomeType;
  run_id: string;
  cmd_line: string;
  is_ci: boolean;
  user: ToolchainUser;
  repo_slug: string;
  ci_info: BuildCIInfo | null;
  link: string;
  machine: string;
  goals: Goal[];
  build_artifacts: BuildArtifacts;
  title?: string;
  indicators?: BuildIndicators;
  download_links: DownloadLink[];
  platform: Platform;
}

export type BuildIndicators = {
  hit_fraction: number;
  saved_cpu_time: number;
  saved_cpu_time_local: number;
  saved_cpu_time_remote: number;
  hit_fraction_local: number;
  hit_fraction_remote: number;
};

export type BuildsListResponse = ApiListResponse<Build>;
export type BuildResponse = {
  run_info: Build;
};
