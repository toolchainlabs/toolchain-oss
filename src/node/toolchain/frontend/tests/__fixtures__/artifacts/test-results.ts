/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { Artifact, PytestResults } from 'common/interfaces/build-artifacts';
import TestOutcomeType from 'common/enums/TestOutcomeType';

export const testResultsPassed: Artifact<PytestResults> = {
  name: 'test_results_with_no_body',
  content_type: 'pytest_results/v2',
  content: {
    test_runs: [
      {
        tests: [
          {
            name: 'pytest one',
            test_file_path: 'first/file',
            time: 546,
            tests: [
              {
                name: 'random1',
                time: 123,
                outcome: TestOutcomeType.PASSED,
              },
              {
                name: 'random2',
                time: 232,
                outcome: TestOutcomeType.PASSED,
              },
              {
                name: 'random3',
                time: 314,
                outcome: TestOutcomeType.PASSED,
              },
            ],
          },
          {
            name: 'pytest one',
            test_file_path: 'second/file',
            time: 123,
            tests: [
              {
                name: 'random1',
                time: 123,
                outcome: TestOutcomeType.PASSED,
              },
            ],
          },
          {
            name: 'pytest one',
            test_file_path: 'third/file',
            time: 123,
            tests: [
              {
                name: 'random1',
                time: 123,
                outcome: TestOutcomeType.PASSED,
              },
            ],
          },
        ],
        outputs: {
          stdout: 'output-1',
          stderr: 'err-1',
        },
        timing: { total: 1.2 },
        target: 'first/target',
      },
    ],
  },
};

export const mixedTestResults: Artifact<PytestResults> = {
  name: 'test_results_with_body_render',
  content_type: 'pytest_results/v2',
  content: {
    test_runs: [
      {
        tests: [
          {
            name: 'pytest two',
            test_file_path: 'second/file',
            time: 2.5,
            tests: [
              {
                name: 'random4',
                time: 0.1,
                outcome: TestOutcomeType.X_FAILED,
                results: [{ message: 'some random message one' }],
              },
              {
                name: 'random6',
                time: 0.2,
                outcome: TestOutcomeType.SKIPPED,
                results: [
                  {
                    message: 'some random message three',
                    text: `Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo. Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo`,
                  },
                ],
              },
              {
                name: 'random7',
                time: 0.3,
                outcome: TestOutcomeType.PASSED,
              },
              {
                name: 'random8',
                time: 0.4,
                outcome: TestOutcomeType.ERROR,
                results: [{ message: 'some random message two', text: 'some random text one' }],
              },
              {
                name: 'random9',
                time: 0.5,
                outcome: TestOutcomeType.X_PASSED,
              },
              {
                name: 'random10',
                time: 0.6,
                outcome: TestOutcomeType.X_PASSED_STRICT,
              },
              {
                name: 'random11',
                time: 0.7,
                outcome: 'random' as TestOutcomeType,
              },
            ],
          },
        ],
        outputs: {
          stdout: 'output-1',
          stderr: 'err-1',
        },
        timing: { total: 1.2 },
        target: 'first/target',
      },
    ],
  },
};

export const mixedTestResultsTwo: Artifact<PytestResults> = {
  name: 'test_results_with_body_render_2',
  content_type: 'pytest_results/v2',
  content: {
    test_runs: [
      {
        tests: [
          {
            name: 'pytest two',
            test_file_path: 'second/file',
            time: 2.8,
            tests: [
              {
                name: 'random4',
                time: 0.1,
                outcome: TestOutcomeType.X_FAILED,
                results: [{ message: 'some random message one' }],
              },
              {
                name: 'random6',
                time: 0.2,
                outcome: TestOutcomeType.SKIPPED,
                results: [
                  {
                    message: 'some random message three',
                    text: `Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo. Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo`,
                  },
                ],
              },
              {
                name: 'random7',
                time: 0.3,
                outcome: TestOutcomeType.PASSED,
              },
              {
                name: 'random8',
                time: 0.4,
                outcome: TestOutcomeType.ERROR,
                results: [{ message: 'some random message two', text: 'some random text one' }],
              },
              {
                name: 'random9',
                time: 0.5,
                outcome: TestOutcomeType.X_PASSED,
              },
              {
                name: 'random10',
                time: 0.6,
                outcome: TestOutcomeType.X_PASSED_STRICT,
              },
              {
                name: 'random11',
                time: 0.7,
                outcome: 'random' as TestOutcomeType,
              },
            ],
          },
          {
            name: 'pytest three',
            test_file_path: 'third/file',
            time: 0.1,
            tests: [
              {
                name: 'random1',
                time: 0.1,
                outcome: TestOutcomeType.X_FAILED,
                results: [{ message: 'some random message one' }],
              },
            ],
          },
          {
            name: 'pytest four',
            test_file_path: 'forth/file',
            time: 0.6,
            tests: [
              {
                name: 'random1',
                time: 0.1,
                outcome: TestOutcomeType.X_FAILED,
                results: [{ message: 'some random message one' }],
              },
              {
                name: 'random2',
                time: 0.2,
                outcome: TestOutcomeType.X_FAILED,
                results: [{ message: 'some random message one' }],
              },
              {
                name: 'random3',
                time: 0.3,
                outcome: TestOutcomeType.X_FAILED,
                results: [{ message: 'some random message one' }],
              },
            ],
          },
        ],
        outputs: {
          stdout: 'output-1',
          stderr: 'err-1',
        },
        timing: { total: 1.2 },
        target: 'first/target',
      },
    ],
  },
};

// This type should the default when the BE migrates
export const testResultsV2: Artifact<PytestResults> = {
  name: 'Test Results',
  content_type: 'pytest_results/v2',
  content: {
    test_runs: [
      {
        tests: [
          {
            name: 'first',
            test_file_path: 'first/file',
            tests: [
              { name: 'first test', time: 0.88, outcome: TestOutcomeType.PASSED },
              {
                results: [{ message: 'random message', text: 'random text' }],
                name: 'second test',
                time: 0.4,
                outcome: TestOutcomeType.X_FAILED,
              },
              {
                name: 'third test',
                time: 0.1,
                outcome: TestOutcomeType.ERROR,
                results: [
                  {
                    message: 'some random message three',
                    text: `Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo. Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo ,Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo. Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo, Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo. Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo, Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo. Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo, Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo. Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo, Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo. Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo`,
                  },
                ],
              },
              {
                name: 'random11',
                time: 0.7,
                outcome: 'random' as TestOutcomeType,
              },
            ],
            time: 1.2,
          },
        ],
        outputs: {
          stdout: 'output-1',
          stderr: 'err-1',
        },
        timing: { total: 1.2 },
        target: 'first/target',
      },
      {
        tests: [
          {
            name: 'second',
            test_file_path: 'second/file',
            tests: [{ name: 'first test', time: 0.09, outcome: TestOutcomeType.PASSED }],
            time: 0.9,
          },
        ],
        outputs: {
          stdout: 'output-2',
          stderr: 'err-2',
        },
        timing: { total: 0.9 },
        target: 'second/target',
      },
      {
        tests: [
          {
            name: 'third',
            test_file_path: 'third/file',
            tests: [
              {
                name: 'first test',
                time: 0.8,
                outcome: TestOutcomeType.X_FAILED,
                results: [{ message: 'some random message one' }],
              },
              {
                name: 'second test',
                time: 0.8,
                outcome: TestOutcomeType.X_FAILED,
                results: [{ message: 'some random message two' }],
              },
              {
                name: 'third test',
                time: 0.8,
                outcome: TestOutcomeType.X_FAILED,
                results: [{ message: 'some random message three' }],
              },
            ],
            time: 2.4,
          },
        ],
        outputs: {
          stdout: 'output-3',
          stderr: 'err-3',
        },
        target: 'third/target',
        timing: { total: 2.4 },
      },
    ],
  },
};

export const testResultsV2TestNames: Artifact<PytestResults> = {
  name: 'Test Results',
  content_type: 'pytest_results/v2',
  content: {
    test_runs: [
      {
        tests: [
          {
            name: 'some_class',
            test_file_path: 'first/file',
            tests: [
              { name: 'some_method', time: 0.88, outcome: TestOutcomeType.PASSED },
              {
                results: [{ message: 'random message', text: 'random text' }],
                name: '1_method',
                time: 0.4,
                outcome: TestOutcomeType.X_FAILED,
              },
              {
                name: './method_one',
                time: 0.1,
                outcome: TestOutcomeType.ERROR,
                results: [
                  {
                    message: 'some random message three',
                    text: `Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo. Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo ,Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo. Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo, Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo. Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo, Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo. Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo, Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo. Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo, Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo. Lorem, ipsum dolor sit amet consectetur adipisicing elit. Provident iste autem porro ullam culpa dolorem, nobis quae? Repellat eius fugit labore ipsum esse laudantium! A, expedita! Explicabo repellat vero, id dolores quo`,
                  },
                ],
              },
            ],
            time: 0.5,
          },
        ],
        outputs: {
          stdout: 'output-1',
          stderr: 'err-1',
        },
        timing: { total: 1.2 },
        target: 'first/file',
      },
    ],
  },
};
