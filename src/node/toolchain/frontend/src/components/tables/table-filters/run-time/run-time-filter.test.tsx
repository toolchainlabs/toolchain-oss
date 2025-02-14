/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { fireEvent, screen } from '@testing-library/react';

import RunTimeFilter from './run-time-filter';
import createMatchMedia from '../../../../../tests/createMatchMedia';
import render from '../../../../../tests/custom-render';

const defaultFieldValue: Array<string | undefined> = [undefined, undefined];
const defaultFieldName = 'run_time';
const defaultFieldLabel = 'Run time';
const onChangeMock = jest.fn();

const renderRunTimeFilter = ({
  fieldValue = defaultFieldValue,
  fieldName = defaultFieldName,
  fieldLabel = defaultFieldLabel,
  onChange = onChangeMock,
}: Partial<React.ComponentProps<typeof RunTimeFilter>> = {}) =>
  render(<RunTimeFilter fieldValue={fieldValue} fieldName={fieldName} onChange={onChange} fieldLabel={fieldLabel} />);

describe('<RunTimeFilter />', () => {
  beforeAll(() => {
    (window.matchMedia as any) = createMatchMedia(window.innerWidth);
  });

  beforeEach(() => onChangeMock.mockClear());

  it('should render the component', () => {
    const { asFragment } = renderRunTimeFilter();

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render the passed label', () => {
    const props = { fieldLabel: 'somelabel' };

    renderRunTimeFilter(props);

    expect(screen.getByText(props.fieldLabel)).toBeInTheDocument();
  });

  it('should render with slider', () => {
    renderRunTimeFilter();

    // Since element with role of slider is not rendered until it has a value
    expect(screen.getByDisplayValue('0')).toBeInTheDocument();
  });

  it('should have no filter state if not filter values are received', () => {
    renderRunTimeFilter();

    expect(screen.getByText('all')).toBeInTheDocument();
  });

  it('should have is longer than state if minimum filter value is passed', () => {
    const props = {
      fieldValue: ['1', undefined],
    };
    renderRunTimeFilter(props);

    expect(screen.getByText('is longer than')).toBeInTheDocument();
  });

  it('should have is shorter than state if maximum filter value is passed', () => {
    const props = {
      fieldValue: [undefined, '120'],
    };
    renderRunTimeFilter(props);

    expect(screen.getByText('is shorter than')).toBeInTheDocument();
  });

  it('should render with slider with passed value', () => {
    const props = {
      fieldValue: [undefined, '20'],
    };

    renderRunTimeFilter(props);
    expect(screen.getByRole('slider')).toHaveAttribute('aria-valuenow', '20');
  });

  it('should render with slider with passed value #2', () => {
    const props = {
      fieldValue: ['120', undefined],
    };

    renderRunTimeFilter(props);
    expect(screen.getByRole('slider')).toHaveAttribute('aria-valuenow', '2');
  });

  it('should use zero as valid value', () => {
    const props = {
      fieldValue: [undefined, '0'],
    };

    renderRunTimeFilter(props);

    expect(screen.getByText('is shorter than')).toBeInTheDocument();
    expect(screen.getByRole('slider')).toHaveAttribute('aria-valuenow', '0');
  });

  it('should use zero as valid value #2', () => {
    const props = {
      fieldValue: ['0', undefined],
    };

    renderRunTimeFilter(props);
    expect(screen.getByText('is longer than')).toBeInTheDocument();
    expect(screen.getByRole('slider')).toHaveAttribute('aria-valuenow', '0');
  });

  it('should initially have no filter state if there is no filters passed', () => {
    renderRunTimeFilter();
    expect(screen.getByText('all')).toBeInTheDocument();
  });

  it('should initially have runTimeTypeTo state if there is maximum value filter passed', () => {
    const props = {
      fieldValue: [undefined, '20'],
    };
    renderRunTimeFilter(props);
    expect(screen.getByText('is shorter than')).toBeInTheDocument();
  });

  it('should initially have runTimeTypeFrom state if there is minimum value filter passed', () => {
    const props = {
      fieldValue: ['120', undefined],
    };
    renderRunTimeFilter(props);
    expect(screen.getByText('is longer than')).toBeInTheDocument();
  });

  it('should call onChangeMock on from input change', () => {
    const props = {
      fieldValue: ['120', undefined],
    };
    renderRunTimeFilter(props);

    const input = screen.getAllByDisplayValue('2')[0];

    fireEvent.input(input, { target: { value: '1' } });

    expect(onChangeMock).toHaveBeenCalledWith({ [defaultFieldName]: ['60', undefined] });
  });

  it('should call onChangeMock on to input change', () => {
    const props = {
      fieldValue: [undefined, '20'],
    };
    renderRunTimeFilter(props);

    const input = screen.getAllByDisplayValue('20')[0];

    fireEvent.input(input, { target: { value: '10' } });

    expect(onChangeMock).toHaveBeenCalledWith({ [defaultFieldName]: [undefined, '10'] });
  });

  it('should call onChangeMock on to slider change', async () => {
    const props = {
      fieldValue: [undefined, '1'],
    };
    renderRunTimeFilter(props);

    const slider = screen.getByRole('slider');
    const sliderRoot = slider.parentElement;

    // As per https://github.com/mui-org/material-ui/issues/23398#issuecomment-723576801
    sliderRoot.getBoundingClientRect = jest.fn(() => ({
      width: 100,
      height: 10,
      bottom: 10,
      left: 0,
      x: 0,
      y: 0,
      right: 0,
      top: 0,
      toJSON: jest.fn(),
    }));

    fireEvent.mouseDown(sliderRoot, { buttons: 1, clientX: 33 });
    fireEvent.mouseUp(sliderRoot, { buttons: 1, clientX: 33 });

    expect(onChangeMock).toHaveBeenCalledWith({ [defaultFieldName]: [undefined, '60'] });

    fireEvent.mouseDown(sliderRoot, { buttons: 1, clientX: 50 });
    fireEvent.mouseUp(sliderRoot, { buttons: 1, clientX: 50 });

    expect(onChangeMock).toHaveBeenCalledWith({ [defaultFieldName]: [undefined, '60'] });
  });

  it('should reset filter on filter type change', () => {
    renderRunTimeFilter();

    fireEvent.change(screen.getByDisplayValue('all'), { target: { value: 'runTypeTo' } });
    expect(onChangeMock).toHaveBeenCalledWith({ [defaultFieldName]: [undefined, '0'] });

    fireEvent.change(screen.getByDisplayValue('runTypeTo'), { target: { value: 'runTypeFrom' } });
    expect(onChangeMock).toHaveBeenCalledWith({ [defaultFieldName]: ['0', undefined] });

    fireEvent.change(screen.getByDisplayValue('runTypeFrom'), { target: { value: 'all' } });
    expect(onChangeMock).toHaveBeenCalledWith({ [defaultFieldName]: [undefined, undefined] });
  });
});
