/*
Copyright 2019 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { Component } from 'react';
import { captureException } from '@sentry/browser';

import ErrorPage from 'pages/error-page';

type SentryErrorBoundaryProps = {
  children: React.ReactNode;
};

type SentryErrorBoundaryState = {
  hasError: boolean;
  eventId: string;
};

class SentryErrorBoundary extends Component<SentryErrorBoundaryProps, SentryErrorBoundaryState> {
  state: SentryErrorBoundaryState = {
    hasError: false,
    eventId: '',
  };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error) {
    // Log the error to Sentry.
    const eventId = captureException(error);
    this.setState({
      eventId,
    });
  }

  render() {
    const { hasError, eventId } = this.state;
    const { children } = this.props;

    if (hasError) {
      return <ErrorPage eventId={eventId} />;
    }
    return children;
  }
}

export default SentryErrorBoundary;
