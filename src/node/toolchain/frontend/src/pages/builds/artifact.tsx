/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { useLocation, useParams } from 'react-router-dom';

import OutcomeType from 'common/enums/OutcomeType';
import backends from 'utils/backend-paths';
import { useQueryGet } from 'utils/hooks/query';
import Console from 'components/console/console';
import LogArtifact from 'components/log-artifact/log-artifact';
import ArtifactTable from 'components/artifact-table/artifact-table';
import { ArtifactsResponse, BuildArtifact } from 'common/interfaces/build-artifacts';
import withLoadingAndError from 'utils/hoc/with-loading-and-error/with-loading-and-error';
import Targets from 'components/targets/targets';
import PantsOptions from 'components/pants-options/pants-options';
import TestResultsWithStdout from 'components/tables/test-results-table-with-stdout/test-results-table-with-stdout';

type LocationState = { user_api_id: string };
type ArtifactContentMap = {
  [key: string]: ({ artifact }: any) => JSX.Element;
};

type ArtifactRenderProps = {
  artifactId: string;
  artifactDescription: string;
  outcome: OutcomeType;
  data?: ArtifactsResponse<any>;
};

const ARTIFACT_COMPONENT_MAP: ArtifactContentMap = {
  'text/plain': Console,
  'text/log': LogArtifact,
  'pytest_results/v2': TestResultsWithStdout,
  work_unit_metrics: ArtifactTable,
  coverage_summary: ArtifactTable,
  targets_specs: Targets,
  pants_options: PantsOptions,
};

export const artifactsContainValidContentType = (artifacts: BuildArtifact[]) =>
  artifacts.some(artifact =>
    artifact.content_types?.some(contentType => Object.keys(ARTIFACT_COMPONENT_MAP).includes(contentType))
  );

const ArtifactRender = ({ artifactId, artifactDescription, outcome, data }: ArtifactRenderProps) => {
  if (!(data && data.length)) {
    return null;
  }

  return (
    <>
      {data.map((artifact, index) => {
        const contentType = artifact.content_type;

        const Component = ARTIFACT_COMPONENT_MAP[contentType];
        if (!Component) {
          return null;
        }

        return (
          <Component
            // eslint-disable-next-line react/no-array-index-key
            key={`${artifactId}-${artifact.name}-${index}`}
            artifact={artifact}
            artifactDescription={artifactDescription}
            outcome={outcome}
          />
        );
      })}
    </>
  );
};

const Artifact = ({
  artifactId,
  artifactDescription,
  outcome,
}: Pick<ArtifactRenderProps, 'artifactId' | 'artifactDescription' | 'outcome'>) => {
  const { orgSlug, repoSlug, runId } = useParams();
  const location = useLocation();
  const { state } = location as { state: LocationState };
  const [{ data, isFetching, errorMessage }] = useQueryGet<ArtifactsResponse<any>>(
    [`${artifactId}/${runId}`],
    backends.buildsense_api.RETRIEVE_BUILD_ARTIFACT(orgSlug, repoSlug, runId, artifactId),
    { ...state },
    {
      staleTime: Infinity,
      cacheTime: Infinity,
    }
  );

  const WrappedComponent = withLoadingAndError(ArtifactRender, data, isFetching, errorMessage, true);
  return <WrappedComponent artifactId={artifactId} artifactDescription={artifactDescription} outcome={outcome} />;
};

export default Artifact;
