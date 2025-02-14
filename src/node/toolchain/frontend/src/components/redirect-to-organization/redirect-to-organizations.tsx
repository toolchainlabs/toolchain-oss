/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { Navigate } from 'react-router-dom';

import { useQueryGet } from 'utils/hooks/query';
import backends from 'utils/backend-paths';
import { ApiListResponse } from 'common/interfaces/api';
import { OrgList } from 'common/interfaces/orgs-repo';
import QueryNames from 'common/enums/QueryNames';
import paths from 'utils/paths';

const RedirectToOrganizationPage = () => {
  const [{ data: orgData }] = useQueryGet<ApiListResponse<OrgList>>(
    [QueryNames.ORGS],
    backends.users_api.LIST_ORGANIZATIONS,
    null,
    { refetchOnMount: false }
  );

  if (!orgData?.results) {
    return null;
  }

  if (orgData.results.length) {
    const slug = orgData.results[0]?.slug;
    return <Navigate replace to={paths.organization(slug)} />;
  }

  return <Navigate replace state={{ fromRedirect: true }} to={paths.noOrganization} />;
};

export default RedirectToOrganizationPage;
