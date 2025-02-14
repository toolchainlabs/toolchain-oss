/*
Copyright 2019 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import MockDate from 'mockdate';

import {
  dateTimeToLocal,
  durationToFormat,
  relativeStringToUtcTime,
  utcTimeAgo,
  utcTimeAgoToRelativeString,
  formatTimeFromSeconds,
  dateTimeAndTimeFromNowLocal,
  isBefore,
  isAfter,
  stringToDate,
  isOlderThan24Hours,
  getMillisecondsHumanized,
  daysLeftUntillDate,
  extendedDateTimeToLocal,
  dateToDateTimeWithSeparator,
} from './datetime-formats';

beforeEach(() => {
  MockDate.set(new Date('2019-05-14T11:01:58.135Z'));
});

afterEach(() => {
  MockDate.reset();
});

describe('dateTimeToLocal', () => {
  it('formats correctly', () => {
    expect(dateTimeToLocal('2019-05-14 10:01:58')).toBe('May 14, 2019 10:01 AM');
  });
});

describe('dateToDateTimeWithSeparator', () => {
  it('formats correctly', () => {
    expect(dateToDateTimeWithSeparator('2019-05-14 10:01:58')).toBe('May 14, 2019 / 10:01 AM');
  });
});

describe('utcTimeAgoToRelativeString', () => {
  it.each([
    ['2019-05-14T10:01:58.135Z', '1 hour ago'],
    ['2019-05-13T11:01:58.135Z', '1 day ago'],
    ['2019-05-07T11:01:58.135Z', '1 week ago'],
    ['2019-05-01T10:01:58.135Z', null],
  ])('converts %i to %s', (duration, result) => {
    expect(utcTimeAgoToRelativeString(duration)).toBe(result);
  });
});

describe('relativeStringToUtcTime', () => {
  it('converts hour correctly', () => {
    const result = relativeStringToUtcTime('1 hour ago');
    expect(result).toEqual('2019-05-14 10:01:58');
  });

  it('converts day correctly', () => {
    const result = relativeStringToUtcTime('1 day ago');
    expect(result).toEqual('2019-05-13 11:01:58');
  });

  it('converts week correctly', () => {
    const result = relativeStringToUtcTime('1 week ago');
    expect(result).toEqual('2019-05-07 11:01:58');
  });

  it('raises an error if passed an incorrect string', () => {
    expect(() => {
      relativeStringToUtcTime('foo');
    }).toThrow();
  });
});

describe('utcTimeAgo', () => {
  it('converts a datetime to a relative string', () => {
    const result = utcTimeAgo('2019-05-10 11:01:58');
    expect(result).toEqual('4 days ago');
  });
});

describe('durationToFormat', () => {
  it.each([
    [5000, '05s'],
    [20000, '20s'],
    [75000, '01m 15s'],
    [200000, '03m 20s'],
    [5764362, '01h 36m 04s'],
    [84963741, '23h 36m 03s'],
  ])('converts %i to %s', (duration, result) => {
    expect(durationToFormat(duration)).toBe(result);
  });
});

describe('formatTimeFromSeconds', () => {
  test.each([
    [undefined, '00:00'],
    ['0', '00:00'],
    ['10', '00:10'],
    ['30', '00:30'],
    ['60', '01:00'],
    ['300', '05:00'],
    ['600', '10:00'],
    ['1200', '20:00'],
    ['1800', '30:00'],
    ['3600', '01:00:00'],
  ])('converts %i string to $expected', (a, expected) => {
    expect(formatTimeFromSeconds(a)).toBe(expected);
  });
});

describe('getMillisecondsHumanized', () => {
  test.each([
    [0, '0 minutes'],
    [10000, 'a minute'],
    [20000, 'a minute'],
    [60000, 'a minute'],
    [90000, '2 minutes'],
    [120000, '2 minutes'],
    [240000, '4 minutes'],
    [1527406, '26 minutes'],
    [347459, '6 minutes'],
    [1179947, '20 minutes'],
  ])('converts %i string to $expected', (a, expected) => {
    expect(getMillisecondsHumanized(a)).toBe(expected);
  });
});

describe('dateTimeAndTimeFromNowLocal', () => {
  it('converts a date to a MMM D, YYYY / HH:MM (timeFrom) A format string', () =>
    expect(dateTimeAndTimeFromNowLocal(new Date().toDateString())).toEqual('May 14, 2019 / 12:00 AM (11 hours ago)'));
});

describe('stringToDate', () => {
  it('converts a date to a M/D/YYYY format', () =>
    expect(stringToDate(new Date().toDateString())).toEqual('5/14/2019'));
});

describe('isBefore', () => {
  it('isBefore should return true', () => {
    const date = new Date();
    const dateTwo = new Date(new Date().setDate(new Date().getDate() + 1));

    expect(isBefore(date.toDateString(), dateTwo.toDateString())).toBe(true);
  });

  it('isBefore should return false', () => {
    const date = new Date();
    const dateTwo = new Date(new Date().setDate(new Date().getDate() - 1));

    expect(isBefore(date.toDateString(), dateTwo.toDateString())).toBe(false);
  });
});

describe('isAfter', () => {
  it('isAfter should return true', () => {
    const date = new Date();
    const dateTwo = new Date(new Date().setDate(new Date().getDate() + 1));

    expect(isAfter(date.toDateString(), dateTwo.toDateString())).toBe(false);
  });

  it('isAfter should return false', () => {
    const date = new Date();
    const dateTwo = new Date(new Date().setDate(new Date().getDate() - 1));

    expect(isAfter(date.toDateString(), dateTwo.toDateString())).toBe(true);
  });
});

describe('isOlderThan24Hours', () => {
  it('isOlderThan24Hours should return true', () => {
    const date = new Date().toISOString();

    expect(isOlderThan24Hours(date)).toBe(true);
  });

  it('isOlderThan24Hours should return false', () => {
    const date = new Date(new Date().setDate(new Date().getDate() - 4)).toISOString();

    expect(isOlderThan24Hours(date)).toBe(false);
  });
});

describe('daysLeftUntillDate', () => {
  test.each([
    [new Date('2019-05-15T11:01:58.135Z').toLocaleDateString(), 0],
    [new Date('2019-05-16T11:01:58.135Z').toLocaleDateString(), 1],
    [new Date('2019-05-20T11:01:58.135Z').toLocaleDateString(), 5],
    [new Date('2019-06-14T11:01:58.135Z').toLocaleDateString(), 30],
  ])('for %p returns %d days left', (a, expected) => {
    expect(daysLeftUntillDate(a)).toBe(expected);
  });
});

describe('get day of the week', () => {
  it('should return proper day of the week', () => {
    const dates = [
      new Date('2022-11-14'),
      new Date('2022-11-15'),
      new Date('2022-11-16'),
      new Date('2022-11-17'),
      new Date('2022-11-18'),
      new Date('2022-11-19'),
      new Date('2022-11-20'),
    ];
    const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

    dates.forEach((date, index) => expect(extendedDateTimeToLocal(date.toString())).toContain(days[index]));
  });
});
