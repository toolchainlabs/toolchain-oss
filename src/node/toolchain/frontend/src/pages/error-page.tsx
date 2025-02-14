/*
Copyright 2019 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';

import ErrorDisplay from 'components/error-display/error-display';

type ErrorPageProps = {
  eventId?: string;
};

const ErrorPage = ({ eventId }: ErrorPageProps) => (
  <ErrorDisplay
    buttonText="go to homepage"
    title="Something went wrong"
    description="This error has been reported to our team. Please try again."
    errorId={eventId}
  />
);

export default ErrorPage;
