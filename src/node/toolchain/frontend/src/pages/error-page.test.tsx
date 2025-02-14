/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen, fireEvent } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';

import ErrorPage from './error-page';
import render from '../../tests/custom-render';

const writeTextMock = jest.fn();

Object.assign(navigator, {
  clipboard: {
    writeText: () => {},
  },
});

jest.spyOn(navigator.clipboard, 'writeText').mockImplementation(writeTextMock);

const renderErrorPage = ({ eventId } = { eventId: '' }) =>
  render(
    <Routes>
      <Route path="*" element={<ErrorPage eventId={eventId} />} />
    </Routes>,
    { wrapperProps: { pathname: '/' } }
  );

describe('<ErrorPage />', () => {
  it('should render the component', () => {
    const { asFragment } = renderErrorPage();

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render the component with event id', () => {
    const { asFragment } = renderErrorPage({ eventId: '123' });

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render something went wrong heading', () => {
    renderErrorPage();

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('should render error description', () => {
    renderErrorPage();

    expect(screen.getByText(/This error has been reported to our team. Please try again./)).toBeInTheDocument();
  });

  it('should render go to homepage button text', () => {
    renderErrorPage();

    expect(screen.getByText('go to homepage')).toBeInTheDocument();
  });

  it('should call writeText with eventId', async () => {
    const mockEventId = '12345';
    renderErrorPage({ eventId: mockEventId });

    fireEvent.click(screen.queryByText(mockEventId));

    expect(writeTextMock).toHaveBeenCalledWith(mockEventId);
  });
});
