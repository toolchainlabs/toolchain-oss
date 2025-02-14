/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClientProvider } from '@tanstack/react-query';
import nock from 'nock';

import TitleFilter from './title-filter';
import render from '../../../../../tests/custom-render';
import queryClient from '../../../../../tests/queryClient';

const TESTING_HOST = 'http://localhost';
const defaultFieldValue: string = undefined;
const defaultFieldName = 'title';
const defaultFieldLabel = 'Title';

const onChangeMock = jest.fn();

jest.mock('utils/init-data', () => ({
  getHost: () => TESTING_HOST,
}));
jest.mock('utils/hooks/access-token');

const renderTitleFilter = ({
  fieldValue = defaultFieldValue,
  fieldName = defaultFieldName,
  fieldLabel = defaultFieldLabel,
  onChange = onChangeMock,
}: Partial<React.ComponentProps<typeof TitleFilter>> = {}) =>
  render(
    <Routes>
      <Route
        path="/"
        element={
          <QueryClientProvider client={queryClient}>
            <TitleFilter fieldValue={fieldValue} fieldName={fieldName} onChange={onChange} fieldLabel={fieldLabel} />
          </QueryClientProvider>
        }
      />
    </Routes>,
    {
      wrapperProps: { pathname: '/' },
      providerProps: {
        orgAndRepo: {
          initRepo: 'toolchain',
          initOrg: 'toolchain',
        },
      },
    }
  );

describe('<TitleFilter />', () => {
  beforeEach(() => {
    queryClient.clear();
    nock.cleanAll();
  });

  afterAll(() => {
    nock.cleanAll();
    nock.restore();
    jest.clearAllMocks();
    queryClient.clear();
  });

  it('should render the component', () => {
    const { asFragment } = renderTitleFilter();

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render with default value passed in fieldValue', async () => {
    const props = {
      fieldValue: 'ra',
    };

    renderTitleFilter(props);

    expect(screen.getByRole('combobox')).toHaveValue(props.fieldValue);
  });

  it('should clear input value on clear click', async () => {
    const props = {
      fieldValue: 'ra',
    };

    renderTitleFilter(props);

    await waitFor(() => expect(screen.getByRole('combobox')).toHaveValue(props.fieldValue));

    fireEvent.click(screen.queryByTitle(/clear/i));

    expect(screen.getByRole('combobox')).not.toHaveValue(props.fieldValue);
    expect(screen.getByRole('combobox')).toHaveValue('');
  });

  it('should change input value and call on change', async () => {
    const user = userEvent.setup();

    renderTitleFilter();

    user.type(screen.getByRole('combobox'), 'Add P');

    await waitFor(() => expect(screen.getByRole('combobox')).toHaveValue('Add P'));

    await waitFor(() => expect(onChangeMock).toHaveBeenCalledWith({ [defaultFieldName]: 'Add P' }));
  });

  it('should display server values as options and call on change on selection', async () => {
    const user = userEvent.setup();
    const text = 'Add';
    const props = {
      fieldValue: text,
    };
    const suggestResponse = {
      values: [
        'Add PR title to PullRequestInfo (#8741)',
        'Add test for buildsense API bug',
        'Add test for buildsense API bug (#8752)',
      ],
    };
    const scope = nock(TESTING_HOST)
      .get('/api/v1/repos/toolchain/toolchain/builds/suggest/')
      .query({ q: text })
      .delay(100)
      .reply(200, suggestResponse);

    renderTitleFilter(props);

    user.click(screen.getByRole('combobox'));

    await screen.findByRole('listbox');

    suggestResponse.values.forEach(value => expect(screen.getByText(value)).toBeInTheDocument());

    user.click(screen.getByText(suggestResponse.values[0]));

    await waitFor(() => expect(screen.getByRole('combobox')).toHaveValue(suggestResponse.values[0]));

    scope.done();
  });
});
