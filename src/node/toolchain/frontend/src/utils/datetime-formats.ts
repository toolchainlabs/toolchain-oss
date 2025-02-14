/*
Copyright 2019 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import dayjs from 'dayjs';
import LocalizedFormat from 'dayjs/plugin/localizedFormat';
import relativeTime from 'dayjs/plugin/relativeTime';
import utc from 'dayjs/plugin/utc';
import durationPlugin from 'dayjs/plugin/duration';

dayjs.extend(LocalizedFormat);
dayjs.extend(relativeTime);
dayjs.extend(utc);
dayjs.extend(durationPlugin);

const DATETIME_FORMAT = 'lll'; // MMM D, YYYY h: mm A
const DATE_FORMAT = 'l'; // M/D/YYYY
const DATE_FORMAT_MONTH = 'll'; // MMM D, YYYY
const TIME_FORMAT = 'LT'; // h:mm A

export const daysLeftUntillDate = (date: string) => dayjs(date).diff(dayjs(), 'd');
export const isOlderThan24Hours = (date: string) => dayjs().diff(date, 'hours', true) < 24;
export const isAfter = (dateOne: string, dateTwo: string) => dayjs(dateOne).isAfter(dayjs(dateTwo));
export const isBefore = (dateOne: string, dateTwo: string) => dayjs(dateOne).isBefore(dayjs(dateTwo));
export const stringToDate = (dateString: string): string => dayjs(dateString).format(DATE_FORMAT);
export const dateTimeToLocal = (dateString: string): string => dayjs(dateString).format(DATETIME_FORMAT);
export const dateToDateTimeWithSeparator = (dateString: string) =>
  `${dayjs(dateString).format(DATE_FORMAT_MONTH)} / ${dayjs(dateString).format(TIME_FORMAT)}`;
export const timeFromNow = (value: string): string => dayjs(value).fromNow().toLocaleLowerCase();
export const dateTimeAndTimeFromNowLocal = (date: string) =>
  `${dayjs(date).format('ll')} / ${dayjs(date).format('LT')} (${timeFromNow(dayjs(date).toString())})`; // MMM D, YYYY / HH:MM A (timeFromNow)
export const utcTimeAgo = (value: string): string => dayjs.utc(value).from(dayjs.utc());
export const utcTimeAgoToRelativeString = (value: string): string | null => {
  // Used to match against available dropdown options for table filters.
  const hoursAgo = dayjs.utc().diff(dayjs.utc(value), 'hour');
  switch (hoursAgo) {
    case 1:
      return '1 hour ago';
    case 24:
      return '1 day ago';
    case 168:
      return '1 week ago';
    default:
      return null;
  }
};
export const relativeStringToUtcTime = (value: string): string => {
  const matches = value.match(/hour|day|week/g);
  return dayjs()
    .utc()
    .subtract(1, matches[0] as any)
    .format('YYYY-MM-DD HH:mm:ss');
};
export const timeBetween = (startUtc: string | number, endUtc: string | number): string =>
  dayjs.utc(startUtc).to(dayjs.utc(endUtc), true);

export const durationToFormat = (durationNumber: number): string => {
  const duration = dayjs.duration(durationNumber);
  const hours = Math.floor(duration.asHours());
  let hoursFormatted = hours < 10 ? `0${hours}h` : `${hours}h`;
  let minutes = duration.minutes();
  let minutesFormatted = minutes < 10 ? `0${minutes}m` : `${minutes}m`;
  let seconds = duration.seconds();
  let secondsFormatted = seconds < 10 ? `0${seconds}s` : `${seconds}s`;

  if (hours >= 1) {
    return `${hoursFormatted} ${minutesFormatted} ${secondsFormatted}`;
  } else if (minutes > 0) {
    return `${minutesFormatted} ${secondsFormatted}`;
  } else {
    return secondsFormatted;
  }
};
export const formatTimeFromSeconds = (value: string) => {
  const seconds = value !== 'undefined' && value !== undefined ? +value : 0;
  const time = dayjs().subtract(seconds, 'second');
  const dur = dayjs.duration(dayjs().diff(time));
  const format = dur.asMilliseconds() < 3600000 ? 'mm:ss' : 'hh:mm:ss';
  let friendlyString = '00:00';

  if (dur.asDays() > 1) {
    friendlyString = `${dur.days()} day${dur.days() > 1 && 's'}`;
  } else {
    friendlyString = dayjs.utc(dur.asMilliseconds()).format(format);
  }

  return friendlyString;
};

export const getMillisecondsHumanized = (milliseconds: number) => {
  // Convert to minutes
  const minutes = Math.ceil(dayjs.duration(milliseconds).asMinutes());

  return minutes ? dayjs.duration(minutes, 'minutes').humanize() : '0 minutes';
};

export const extendedDateTimeToLocal = (date: string) => {
  return `${dayjs(date).format('dddd')}, ${dateTimeToLocal(date)}`;
};
