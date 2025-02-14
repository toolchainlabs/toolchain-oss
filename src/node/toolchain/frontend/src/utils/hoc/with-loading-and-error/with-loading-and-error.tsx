/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useState } from 'react';
import LinearProgress from '@mui/material/LinearProgress';
import Snackbar from '@mui/material/Snackbar';
import { styled } from '@mui/material/styles';

import { useRequestErrorContext } from 'store/request-error-store';

const StyledLinearProgress = styled(LinearProgress)(({ theme }) => ({
  width: '100%',
  maxHeight: theme.spacing(0.5),
  marginTop: theme.spacing(5),
}));

const withLoadingAndError =
  <P extends object>(
    component: React.ComponentType<P>,
    data: any,
    isLoading: boolean,
    errorMessage: string | null,
    isArtifactComponent?: boolean
  ): React.FC<P> =>
  (props: P) => {
    const { setErrorMessage } = useRequestErrorContext();
    const [showError, toggleShowError] = useState(true);

    if (isLoading) {
      return isArtifactComponent ? <StyledLinearProgress /> : <LinearProgress />;
    }

    if (showError && errorMessage) {
      return (
        <Snackbar
          anchorOrigin={{
            vertical: 'top',
            horizontal: 'center',
          }}
          open={showError}
          onClose={() => {
            toggleShowError(false);
            setErrorMessage(null);
          }}
          message={errorMessage}
        />
      );
    }

    if (!data) {
      return null;
    }

    const Component = component;

    // eslint-disable-next-line react/jsx-props-no-spreading
    return <Component data={data} {...props} />;
  };

export default withLoadingAndError;
