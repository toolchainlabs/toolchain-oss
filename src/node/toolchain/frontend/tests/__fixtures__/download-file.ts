/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

export const traceData = [
  {
    traceId: 'pants_run_2021_08_12_16_12_59_697_01f4fe855ac14720b047408348f94e17',
    name: 'first_trace',
    id: 'aa90323f1731b10c',
    timestamp: 1628809980048434,
    duration: 6931,
    localEndpoint: { serviceName: 'select' },
  },
  {
    traceId: 'pants_run_2021_08_12_16_12_59_697_01f4fe855ac14720b047408348f94e17',
    name: 'second_trace',
    id: '8eba0a69ccca0373',
    timestamp: 1628809980048470,
    duration: 6879,
    localEndpoint: { serviceName: 'pants.engine.streaming_workunit_handler.construct_workunits_callback_factories' },
    parentId: 'aa90323f1731b10c',
  },
  {
    traceId: 'pants_run_2021_08_12_16_12_59_697_01f4fe855ac14720b047408348f94e17',
    name: 'third_trace',
    id: 'f0a62e61a43b1b56',
    timestamp: 1628809980048499,
    duration: 10,
    localEndpoint: { serviceName: 'pants.init.engine_initializer.union_membership_singleton' },
    parentId: '8eba0a69ccca0373',
  },
  {
    traceId: 'pants_run_2021_08_12_16_12_59_697_01f4fe855ac14720b047408348f94e17',
    name: 'fourth_trace',
    id: 'd460bc4f0cbfcc62',
    timestamp: 1628809980048758,
    duration: 6544,
    localEndpoint: { serviceName: 'toolchain.pants.buildsense.reporter.construct_buildsense_callback' },
    parentId: '8eba0a69ccca0373',
  },
];

export const workunits = [
  {
    traceId: 'pants_run_2021_08_12_16_12_59_697_01f4fe855ac14720b047408348f94e17',
    name: 'first_trace',
    id: 'aa90323f1731b10c',
    timestamp: 1628809980048434,
    duration: 6931,
    localEndpoint: { serviceName: 'select' },
  },
  {
    traceId: 'pants_run_2021_08_12_16_12_59_697_01f4fe855ac14720b047408348f94e17',
    name: 'second_trace',
    id: '8eba0a69ccca0373',
    timestamp: 1628809980048470,
    duration: 6879,
    localEndpoint: { serviceName: 'pants.engine.streaming_workunit_handler.construct_workunits_callback_factories' },
    parentId: 'aa90323f1731b10c',
  },
  {
    traceId: 'pants_run_2021_08_12_16_12_59_697_01f4fe855ac14720b047408348f94e17',
    name: 'third_trace',
    id: 'f0a62e61a43b1b56',
    timestamp: 1628809980048499,
    duration: 10,
    localEndpoint: { serviceName: 'pants.init.engine_initializer.union_membership_singleton' },
    parentId: '8eba0a69ccca0373',
  },
  {
    traceId: 'pants_run_2021_08_12_16_12_59_697_01f4fe855ac14720b047408348f94e17',
    name: 'fourth_trace',
    id: 'd460bc4f0cbfcc62',
    timestamp: 1628809980048758,
    duration: 6544,
    localEndpoint: { serviceName: 'toolchain.pants.buildsense.reporter.construct_buildsense_callback' },
    parentId: '8eba0a69ccca0373',
  },
];
