/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { Artifact, TargetsContent } from 'common/interfaces/build-artifacts';

export const targets: Artifact<TargetsContent> = {
  content_type: 'targets_specs',
  name: 'Targets',
  content: {
    'folder1/subfolder1a/subfolder1b/': {
      subfolder1c: [
        {
          filename: 'file100.py',
        },
        {
          filename: 'file110.py',
        },
      ],
      subfolder2c: [
        {
          filename: 'file200.py',
        },
        {
          filename: 'file210.py',
        },
      ],
    },
    'folder2/subfolder2a/subfolder2b/': {
      subfolder3c: [
        {
          filename: 'file300.py',
        },
        {
          filename: 'file310.py',
        },
        {
          filename: 'file320.py',
        },
      ],
      subfolder4c: [
        {
          filename: 'file400.py',
        },
        {
          filename: 'file410.py',
        },
      ],
    },
    folder3: [
      {
        filename: 'file500.py',
      },
    ],
    folder4: [] as any[],
  },
};

export const targetsOnlyOneFolder: Artifact<TargetsContent> = {
  content_type: 'targets_specs',
  name: 'Targets',
  content: [
    {
      filename: 'file100.py',
    },
    {
      filename: 'file110.py',
    },
    {
      filename: 'file120.py',
    },
    {
      filename: 'file130.py',
    },
  ],
};

export const targetsEmpty: Artifact<TargetsContent> = {
  content_type: 'targets_specs',
  name: 'Targets',
  content: null,
};
