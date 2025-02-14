/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { BuildArtifact } from 'common/interfaces/build-artifacts';
import OutcomeType from 'common/enums/OutcomeType';
import RunType from 'common/enums/RunType';
import { Build, GoalData } from 'common/interfaces/builds';
import branches from './branches';
import goals from './goals';
import users from './users';

const generateLintBuildArtifact = (): GoalData => ({
  artifacts: [
    {
      description: 'first lint',
      name: 'lorem-ipsum-1.json',
      group: 'lint',
    },
    {
      description: 'second lint',
      name: 'lorem-ipsum-2.json',
      group: 'lint',
      content_types: ['text/plain'],
    },
    {
      description: 'third lint',
      name: 'lorem-ipsum-3.json',
      group: 'lint',
      content_types: ['text/plain'],
    },
  ],
  type: 'goal',
});

const generateTypecheckBuildArtifact = (): GoalData => ({
  artifacts: [
    {
      description: 'first typecheck',
      name: 'lorem-ipsum-4.json',
      group: 'typecheck',
      content_types: ['text/plain'],
    },
  ],
  type: 'goal',
});

const generateMetricsBuildArtifact = (): GoalData => ({
  artifacts: [
    {
      name: 'aggregated_workunit_metrics.json',
      description: 'Run metrics',
      content_types: ['work_unit_metrics'],
    },
  ],
  type: 'run',
});

const generateTestBuildArtifactWithOutput = (): GoalData => ({
  artifacts: [
    {
      description: 'Run Pytest',
      name: 'test_1_artifacts.json',
      result: 'SUCCESS',
      group: 'pants.backend.python.goals.pytest_runner.run_python_test',
      content_types: ['text/plain'],
    },
    {
      description: 'Run Pytest',
      name: 'test_2_artifacts.json',
      result: 'SUCCESS',
      group: 'pants.backend.python.goals.pytest_runner.run_python_test',
      content_types: ['text/plain'],
    },
    {
      description: 'Run Pytest',
      name: 'test_3_artifacts.json',
      result: 'FAILURE',
      group: 'pants.backend.python.goals.pytest_runner.run_python_test',
      content_types: ['text/plain'],
    },
    {
      description: 'Code Coverage Summary',
      name: 'coverage_summary.json',
      group: 'coverage_summary',
      content_types: ['coverage_summary'],
    },
    {
      description: 'Test results',
      name: 'pytest_results_v2.json',
      group: 'pytest_results',
      content_types: ['pytest_results/v2'],
    },
  ],
  type: 'goal',
});

const generateTargetsBuildArtifact = (): GoalData => ({
  artifacts: [
    {
      description: 'Expanded targets specs',
      name: 'targets_specs.json',
      group: 'targets_specs',
      content_types: ['targets_specs'],
    },
  ],
  type: 'run',
});

const generateRandomArtifact = (
  aditionalArtifacts: BuildArtifact[] = [] as any,
  artifactType: string = 'goal'
): GoalData => ({
  artifacts: [
    {
      name: 'random.json',
      description: 'Random artifact',
      content_types: ['random_content_type'],
    },
    ...aditionalArtifacts,
  ],
  type: artifactType,
});

const generatePantsOptions = (): GoalData => ({
  artifacts: [
    {
      description: 'Pants Options',
      name: 'pants_options.json',
      group: 'pants_options',
      content_types: ['pants_options'],
    },
  ],
  type: 'run',
});

const generateBuild = (overrides: any): Build => ({
  branch: branches[0],
  datetime: '2020-05-12T17:14:51+00:00',
  run_time: 16492,
  outcome: OutcomeType.SUCCESS,
  run_id: 'pants_run_2020_05_12_10_14_51_642_86dcSgQTwIFX0pi2KnUx',
  cmd_line: 'some command a',
  is_ci: false,
  user: users[0],
  goals: [goals[0], goals[1], goals[2]],
  repo_slug: 'repo-slug-1',
  ci_info: null,
  link: 'localhost',
  machine: 'some-machine',
  build_artifacts: {},
  platform: {
    architecture: 'arm64',
    cpu_count: 10,
    mem_bytes: 68719476736,
    os: 'Darwin',
    os_release: '21.5.0',
    processor: 'arm',
    python_implementation: 'CPython',
    python_version: '3.9.12',
  },
  ...overrides,
});

const buildsList: Build[] = [
  generateBuild({
    outcome: OutcomeType.SUCCESS,
    run_id: 'pants_run_2020_05_12_10_14_51_642_86dcSgQTwIFX0pi2KnUx_1',
    build_artifacts: {
      metrics: generateMetricsBuildArtifact(),
      lint: generateLintBuildArtifact(),
      typecheck: generateTypecheckBuildArtifact(),
    },
    download_links: [
      {
        name: 'trace',
        link: '/api/v1/repos/toolchaindev/toolchain/builds/run_id_testing/trace/',
      },
      {
        name: 'workunits',
        link: '/api/v1/repos/toolchaindev/toolchain/builds/run_id_testing/workunits/',
      },
    ],
  }),
  generateBuild({
    outcome: OutcomeType.RUNNING,
    run_id: 'pants_run_2020_05_12_10_14_51_642_86dcSgQTwIFX0pi2KnUx_2',
    build_artifacts: { lint: generateLintBuildArtifact(), random: generateRandomArtifact() },
    goals: [goals[0]],
    datetime: '2020-05-09T03:44:14+00:00',
    branch: branches[1],
  }),
  generateBuild({
    outcome: OutcomeType.FAILURE,
    run_id: 'pants_run_2020_05_12_10_14_51_642_86dcSgQTwIFX0pi2KnUx_3',
    build_artifacts: {
      lint: generateLintBuildArtifact(),
      random: generateRandomArtifact([
        {
          name: 'random-two.json',
          description: 'Second random artifact',
          content_types: ['text/plain'],
        },
      ]),
    },
    branch: branches[2],
    user: users[1],
    is_ci: true,
    goals: [goals[0], goals[1]],
    ci_info: {
      username: users[1].username,
      run_type: RunType.PULL_REQUEST,
      pull_request: 1234,
      job_name: 'build',
      build_num: 431465,
      links: [
        { icon: 'github', text: 'github text', link: 'https://github.com/' },
        { icon: 'travis-ci', text: 'travis text', link: 'https://travis-ci.com/' },
      ],
    },
  }),
  generateBuild({
    run_time: null,
    run_id: 'pants_run_2020_05_12_10_14_51_642_86dcSgQTwIFX0pi2KnUx_4',
    outcome: OutcomeType.ABORTED,
    is_ci: true,
    user: users[2],
    goals: [],
    repo_slug: 'repo-slug-2',
    ci_info: {
      username: users[2].username,
      run_type: RunType.BRANCH,
      pull_request: 5367,
      job_name: 'build',
      build_num: 586754,
      links: [
        { icon: 'github', text: 'github text', link: 'https://github.com/' },
        { icon: 'travis-ci', text: 'travis text', link: 'https://travis-ci.com/' },
      ],
    },
    build_artifacts: { lint: generateLintBuildArtifact() },
  }),
  generateBuild({
    branch: branches[1],
    run_id: 'pants_run_2020_05_12_10_14_51_642_86dcSgQTwIFX0pi2KnUx_5',
    datetime: '2020-03-09T02:53:40+00:00',
    run_time: null,
    outcome: OutcomeType.NOT_AVAILABLE,
    user: users[2],
    goals: [],
    repo_slug: 'repo-slug-3',
    build_artifacts: { lint: generateLintBuildArtifact() },
  }),
  generateBuild({
    run_time: null,
    run_id: 'pants_run_2020_05_12_10_14_51_642_86dcSgQTwIFX0pi2KnUx_6',
    outcome: OutcomeType.ABORTED,
    is_ci: true,
    user: users[2],
    goals: [],
    repo_slug: 'repo-slug-7',
    ci_info: {
      username: users[2].username,
      run_type: RunType.BRANCH,
      pull_request: 5368,
      job_name: 'build',
      build_num: 586755,
      links: [
        { icon: 'github', text: 'github text', link: 'https://github.com/' },
        { icon: 'travis-ci', text: 'travis text', link: 'https://travis-ci.com/' },
      ],
    },
  }),
  generateBuild({
    run_time: null,
    outcome: OutcomeType.ABORTED,
    is_ci: true,
    user: users[2],
    goals: [],
    run_id: 'pants_run_2020_05_12_10_14_51_642_86dcSgQTwIFX0pi2KnUx_7',
    repo_slug: 'repo-slug-7',
    ci_info: {
      username: users[2].username,
      run_type: RunType.BRANCH,
      pull_request: 5368,
      job_name: 'build',
      build_num: 586755,
      links: [
        { icon: 'github', text: 'github text', link: 'https://github.com/' },
        { icon: 'travis-ci', text: 'travis text', link: 'https://travis-ci.com/' },
      ],
    },
  }),
  generateBuild({
    run_time: null,
    outcome: OutcomeType.ABORTED,
    is_ci: true,
    user: users[2],
    goals: [],
    repo_slug: 'repo-slug-7',
    run_id: 'pants_run_2020_05_12_10_14_51_642_86dcSgQTwIFX0pi2KnUx_8',
    ci_info: {
      username: users[2].username,
      run_type: RunType.BRANCH,
      pull_request: 5368,
      job_name: 'build',
      build_num: 586755,
      links: [
        { icon: 'github', text: 'github text', link: 'https://github.com/' },
        { icon: 'travis-ci', text: 'travis text', link: 'https://travis-ci.com/' },
      ],
    },
  }),
  generateBuild({
    run_time: null,
    run_id: 'pants_run_2020_05_12_10_14_51_642_86dcSgQTwIFX0pi2KnUx_9',
    outcome: OutcomeType.ABORTED,
    is_ci: true,
    user: users[2],
    goals,
    repo_slug: 'repo-slug-7',
    ci_info: {
      username: users[2].username,
      run_type: RunType.BRANCH,
      pull_request: 5368,
      job_name: 'build',
      build_num: 586755,
      links: [
        { icon: 'github', text: 'github text', link: 'https://github.com/' },
        { icon: 'travis-ci', text: 'travis text', link: 'https://travis-ci.com/' },
      ],
    },
    build_artifacts: { lint: generateLintBuildArtifact(), test: generateTestBuildArtifactWithOutput() },
  }),
  generateBuild({
    run_id: 'pants_run_2020_05_12_10_14_51_642_86dcSgQTwIFX0pi2KnUx_10',
    outcome: OutcomeType.ABORTED,
    is_ci: false,
    user: users[2],
    goals,
    repo_slug: 'repo-slug-7',
    build_artifacts: {
      metrics: generateMetricsBuildArtifact(),
      lint: generateLintBuildArtifact(),
      typecheck: generateTypecheckBuildArtifact(),
      targets_specs: generateTargetsBuildArtifact(),
    },
  }),
  generateBuild({
    outcome: OutcomeType.SUCCESS,
    run_id: 'pants_run_2020_05_12_10_14_51_642_86dcSgQTwIFX0pi2KnUx_11',
    build_artifacts: {
      metrics: generateMetricsBuildArtifact(),
      lint: generateLintBuildArtifact(),
      typecheck: generateTypecheckBuildArtifact(),
      pants_options: generatePantsOptions(),
    },
    run_time: 9492,
  }),
  generateBuild({
    outcome: OutcomeType.SUCCESS,
    run_id: 'pants_run_2020_05_12_10_14_51_642_86dcSgQTwIFX0pi2KnUx_13',
    build_artifacts: {
      random: generateRandomArtifact(),
      radomTwo: generateRandomArtifact(),
    },
    run_time: 13492,
  }),
  generateBuild({
    outcome: OutcomeType.SUCCESS,
    run_id: 'pants_run_2020_05_12_10_14_51_642_86dcSgQTwIFX0pi2KnUx_14',
    build_artifacts: {
      random: generateRandomArtifact([], 'run'),
      radomTwo: generateRandomArtifact([], 'run'),
    },
    run_time: 13492,
  }),
  generateBuild({
    outcome: OutcomeType.SUCCESS,
    run_id: 'pants_run_2020_05_12_10_14_51_642_86dcSgQTwIFX0pi2KnUx_15',
    run_time: 13492,
    indicators: {
      used_cpu_time: 22000,
      saved_cpu_time: 120000,
      hit_fraction: 0.5012,
      saved_cpu_time_local: 90000,
      saved_cpu_time_remote: 30000,
      hit_fraction_local: 0.2506,
      hit_fraction_remote: 0.2506,
    },
  }),
  generateBuild({
    outcome: OutcomeType.SUCCESS,
    run_id: 'pants_run_2020_05_12_10_14_51_642_86dcSgQTwIFX0pi2KnUx_16',
    run_time: 13492,
    indicators: {
      used_cpu_time: 11000,
      saved_cpu_time: 60000,
      hit_fraction: 0.2512,
      saved_cpu_time_local: 35000,
      saved_cpu_time_remote: 15000,
      hit_fraction_local: 0.1206,
      hit_fraction_remote: 0.1206,
    },
    build_artifacts: { lint: generateLintBuildArtifact(), test: generateTestBuildArtifactWithOutput() },
  }),
];

export default buildsList;
