/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { fireEvent, screen } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';

import HomePage from 'pages/home-page';
import ErrorDisplay from './error-display';
import render from '../../../tests/custom-render';

const writeTextMock = jest.fn();

const mockErrorRoute = '/error/';
const mockButtonText = 'try again';
const mockTitle = 'some title';
const mockDescription = 'some description';
const mockErrorId = '123';

const MockSomeRoute = () => <span>Some Route</span>;

Object.assign(navigator, {
  clipboard: {
    writeText: () => {},
  },
});

jest.spyOn(navigator.clipboard, 'writeText').mockImplementation(writeTextMock);

const renderErrorDisplay = (
  initRoute: string = mockErrorRoute,
  errorDisplayProps: { buttonText: string; title: string; description: string; errorId?: string; goBackUrl: string } = {
    buttonText: mockButtonText,
    title: mockTitle,
    description: mockDescription,
    goBackUrl: '/',
  }
) => {
  const { buttonText, title, description, errorId, goBackUrl } = errorDisplayProps;
  return render(
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route
        path={mockErrorRoute}
        element={
          <ErrorDisplay
            buttonText={buttonText}
            title={title}
            description={description}
            errorId={errorId}
            goBackUrl={goBackUrl}
          />
        }
      />
      <Route path="/some-route/" element={<MockSomeRoute />} />
    </Routes>,
    { wrapperProps: { pathname: initRoute } }
  );
};

describe('<ErrorDisplay />', () => {
  it('should render the component', () => {
    const { asFragment } = renderErrorDisplay();

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render errorId', () => {
    renderErrorDisplay(mockErrorRoute, {
      buttonText: mockButtonText,
      title: mockTitle,
      description: mockDescription,
      goBackUrl: '',
      errorId: mockErrorId,
    });

    expect(screen.getByText(mockErrorId)).toBeInTheDocument();
  });

  it('should render email link with subject', () => {
    renderErrorDisplay(mockErrorRoute, {
      buttonText: mockButtonText,
      title: mockTitle,
      description: mockDescription,
      goBackUrl: '',
      errorId: mockErrorId,
    });

    expect(screen.queryByText('support@toolchain.com').closest('a')).toHaveAttribute(
      'href',
      `mailto:support@toolchain.com?subject=${mockTitle}. Request id: ${mockErrorId}`
    );
  });

  it('should render title, description and button text', async () => {
    renderErrorDisplay();

    expect(screen.getByText(mockTitle)).toBeInTheDocument();
    expect(screen.getByText(/some description/)).toBeInTheDocument();
    expect(screen.getByText(mockButtonText)).toBeInTheDocument();
  });

  it('should call writeText with requestId', () => {
    renderErrorDisplay(mockErrorRoute, {
      buttonText: mockButtonText,
      title: mockTitle,
      description: mockDescription,
      goBackUrl: '',
      errorId: mockErrorId,
    });

    fireEvent.click(screen.queryByText(mockErrorId));

    expect(writeTextMock).toHaveBeenCalledWith(mockErrorId);
  });

  it('should redirect to homepage on button click', async () => {
    renderErrorDisplay();

    fireEvent.click(screen.queryByText(mockButtonText));

    await screen.findByText('Welcome to Toolchain!');
    expect(screen.getByText('Welcome to Toolchain!')).toBeInTheDocument();
  });

  it('should redirect to goBack url on button click', async () => {
    renderErrorDisplay(mockErrorRoute, {
      buttonText: mockButtonText,
      title: mockTitle,
      description: mockDescription,
      goBackUrl: '/some-route/',
      errorId: mockErrorId,
    });

    fireEvent.click(screen.queryByText(mockButtonText));

    await screen.findByText('Some Route');
    expect(screen.getByText('Some Route')).toBeInTheDocument();
  });
});
