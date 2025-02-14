/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { Artifact, ConsoleContent, EnvName } from 'common/interfaces/build-artifacts';

export const textPlain: Artifact<ConsoleContent> = {
  name: 'first-name',
  content: '\u001b[34mhello world from plain content',
  content_type: 'text/plain',
};

export const textPlainTwo: Artifact<ConsoleContent> = {
  name: 'second-name',
  content: '\u001b[34mhello world from plain second content',
  content_type: 'text/plain',
};

export const textPlainThree: Artifact<ConsoleContent> = {
  name: 'third-name',
  content: '\u001b[34mhello world from plain third content',
  content_type: 'text/plain',
};

export const textPlainFour: Artifact<ConsoleContent> = {
  name: 'fourth-name',
  content: '\u001b[34mhello world from plain fourth content',
  content_type: 'text/plain',
};

export const textPlainNoContentType: Artifact<ConsoleContent> = {
  name: 'No content type',
  content: '\u001b[34mhello world from no content type',
  content_type: null,
};

export const textLog: Artifact<ConsoleContent> = {
  content_type: 'text/log',
  name: 'Pants run log',
  content:
    '14:58:49.85 \u001b[31m[WARN]\u001b[0m File watcher exiting with: The watcher was shut down.\n14:58:50.60 \u001b[31m[WARN]\u001b[0m Failed to write to remote cache (1 occurrences so far): Unknown: "transport error: error trying to connect: tcp connect error: Connection refused (os error 61)"\n14:58:50.98 \u001b[31m[WARN]\u001b[0m Failed to read from remote cache (1 occurrences so far): Unknown: "transport error: error trying to connect: tcp connect error: Connection refused (os error 61)',
};

export const textPlainWrongContentType: Artifact<ConsoleContent> = {
  name: 'Wrong_content_type',
  content: '\u001b[34mhello world from wrong content type',
  content_type: 'text/xml',
};

export const artifactFromLocalCache: Artifact<ConsoleContent> = {
  name: 'first-name',
  content: '\u001b[34mhello world from plain content',
  content_type: 'text/plain',
  from_cache: true,
  env_name: EnvName.LOCAL,
  timing_msec: { run_time: 4, start_time: 2792 },
};

export const artifactFromRemoteCache: Artifact<ConsoleContent> = {
  name: 'first-name',
  content: '\u001b[34mhello world from plain content',
  content_type: 'text/plain',
  from_cache: true,
  env_name: EnvName.REMOTE,
  timing_msec: { run_time: 4, start_time: 2792 },
};

export const artifactRemoteExecution: Artifact<ConsoleContent> = {
  name: 'first-name',
  content: '\u001b[34mhello world from plain content',
  content_type: 'text/plain',
  from_cache: false,
  env_name: EnvName.REMOTE,
  timing_msec: { run_time: 543, start_time: 400 },
};

export const artifactLocalExecution: Artifact<ConsoleContent> = {
  name: 'first-name',
  content: '\u001b[34mhello world from plain content',
  content_type: 'text/plain',
  from_cache: false,
  env_name: EnvName.LOCAL,
  timing_msec: { run_time: 1543, start_time: 400 },
};

export const artifactOnlyTimings: Artifact<ConsoleContent> = {
  name: 'first-name',
  content: '\u001b[34mhello world from plain content',
  content_type: 'text/plain',
  timing_msec: { run_time: 1543, start_time: 400 },
};

export const artifactRandomEnvName: Artifact<ConsoleContent> = {
  name: 'first-name',
  content: '\u001b[34mhello world from plain content',
  content_type: 'text/plain',
  from_cache: false,
  env_name: 'Random',
  timing_msec: { run_time: 1543, start_time: 400 },
};
