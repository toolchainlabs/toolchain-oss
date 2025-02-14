/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';

import CacheIndicators from './cache-indicators';
import buildsList from '../../../tests/__fixtures__/builds-list';
import render from '../../../tests/custom-render';

const { indicators: defaultIndicators } = buildsList[13];

const renderCacheIndications = ({
  indicators = null,
  displayTimeSaved = true,
  loading = false,
}: Partial<React.ComponentProps<typeof CacheIndicators>> = {}) =>
  render(<CacheIndicators indicators={indicators} displayTimeSaved={displayTimeSaved} loading={loading} />);

describe('<CacheIndications />', () => {
  it('should render component', () => {
    const { asFragment } = renderCacheIndications({ indicators: defaultIndicators });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render cache hitrate', () => {
    renderCacheIndications({ indicators: defaultIndicators });

    expect(screen.getByText('50% from cache')).toBeInTheDocument();
  });

  it('should render cpu saved time', () => {
    renderCacheIndications({ indicators: defaultIndicators });

    expect(screen.getByText('2 minutes saved')).toBeInTheDocument();
  });

  it('should render time saved tooltip text', async () => {
    renderCacheIndications({ indicators: defaultIndicators });

    fireEvent.mouseOver(screen.queryByText('2 minutes saved'));

    await screen.findByText('2 minutes CPU time saved');

    expect(screen.getByText('2 minutes of cpu time was saved in this build')).toBeInTheDocument();
    expect(screen.getByText('* 2 minutes by local cache')).toBeInTheDocument();
    expect(screen.getByText('* a minute by Toolchain cache')).toBeInTheDocument();
  });

  it('should render cache hit tooltip text', async () => {
    renderCacheIndications({ indicators: defaultIndicators });

    fireEvent.mouseOver(screen.queryByText('50% from cache'));

    await screen.findByText('50% cache hit rate');

    expect(screen.getByText('50% of processes in this build were served from cache')).toBeInTheDocument();
    expect(screen.getByText('* 25% hit rate for local cache')).toBeInTheDocument();
    expect(screen.getByText('* 25% hit rate for Toolchain cache')).toBeInTheDocument();
  });

  it('should not render time saved text or tooltip text', async () => {
    renderCacheIndications({ displayTimeSaved: false, indicators: defaultIndicators });

    fireEvent.mouseOver(screen.queryByText('50% from cache'));

    await waitFor(() => {
      expect(screen.queryByText('2 minutes CPU time saved')).not.toBeInTheDocument();
    });

    expect(screen.queryByText('2 minutes saved')).not.toBeInTheDocument();
  });

  it('should render data not available', async () => {
    renderCacheIndications({ indicators: null });

    expect(screen.getByText('Data not available')).toBeInTheDocument();
  });

  it('should render data loading not available', async () => {
    renderCacheIndications({ loading: true });

    expect(screen.getByText('Data loading...')).toBeInTheDocument();
  });
});
