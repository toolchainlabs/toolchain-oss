/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { Artifact, ConsoleContent } from 'common/interfaces/build-artifacts';
import CodeBlock from 'components/codeblock/codeblock';
import ArtifactCard from 'pages/builds/artifact-card';
import OutcomeType from 'common/enums/OutcomeType';

type ConsoleProps = {
  artifact: Artifact<ConsoleContent>;
  artifactDescription: string;
  outcome: OutcomeType;
};

const Console = ({ artifact, artifactDescription, outcome }: ConsoleProps) => (
  <ArtifactCard description={artifactDescription} outcome={outcome} showOutcome artifact={artifact}>
    <CodeBlock convertAnsi={true}>{artifact.content}</CodeBlock>
  </ArtifactCard>
);

export default Console;
