// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).
/*
Copyright 2017 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

var toolchain = toolchain || {};

toolchain.site = toolchain.site || {};

toolchain.site.util = toolchain.site.util || {};

toolchain.site.util._dateFmt = 'YYYY/MM/DD';
toolchain.site.util._timeFmt = 'HH:mm:ss';
toolchain.site.util._millisFmt = '.SSS';

toolchain.site.util.dateToStr = function(val, withMillis) {
  if (!val) {
    return '';
  }
  var dt = moment(val).utc();
  if (dt.isSame(moment(0))) {
    return '-';  // This is the UNIX epoch.
  }
  var fmt = toolchain.site.util._dateFmt + ' ' + toolchain.site.util._timeFmt;
  if (withMillis) {
    fmt += toolchain.site.util._millisFmt;
  }
  return dt.format(fmt);
};

toolchain.site.util.dateToStrWithMillis = function(val) {
  return toolchain.site.util.dateToStr(val, true);
};

toolchain.site.util.shortenDateTime = function(val, withMillis) {
  var dt_str = toolchain.site.util.dateToStr(val, withMillis);

  function maybeTruncate(prefix) {
    if (dt_str.startsWith(prefix)) {
      dt_str = dt_str.substring(prefix.length);
      return true;
    }
    return false;
  }

  var now = moment().utc();
  var today = now.format(toolchain.site.util._dateFmt);
  if (!maybeTruncate(today + ' ')) {
    maybeTruncate(now.year() + '/');
  }
  return dt_str;
};

toolchain.site.util.shortenDateTimeWithMillis = function(val) {
  return toolchain.site.util.shortenDateTime(val, true);
};

toolchain.site.util.elapsedSince = function(val, withMillis) {
  if (!val) {
    return '';
  }
  var diffMillis = moment().diff(val);
  var ms = diffMillis % 1000;
  var diffSecs = Math.floor(diffMillis / 1000);
  var secs = diffSecs % 60;
  var diffMins = Math.floor(diffSecs / 60);
  var mins = diffMins % 60;
  var diffHours = Math.floor(diffMins / 60);
  var hours = diffHours % 24;
  var days = Math.floor(diffHours / 24);

  var ret = '';

  function pad(num, len) {
    var str = num.toString();
    // Only pad if there's a prefix. E.g., 1m02.123s, but just 2.123s.
    return (ret !== '' && str.length < len) ? pad('0' + str, len) : str;
  }

  var numParts = 0;

  if (days > 0) {
    ret = ret + days.toString() + 'd';
    numParts += 1;
  }
  if (hours > 0) {
    ret = ret + pad(hours, 2) + 'h';
    numParts += 1;
  }
  if (numParts < 2) {
    if (mins > 0) {
      ret = ret + pad(mins, 2) + 'm';
      numParts += 1;
    }
    if (numParts < 2) {
      if (secs > 0) {
        ret = ret + pad(secs, 2);
        numParts += 1;
      }
      if (numParts < 2) {
        if (ret === '') {
          ret = '0';
        }
        if (withMillis) {
          ret = ret + '.' + pad(ms, 3);
          numParts += 1;
        }
        ret = ret + 's';
      }
    }
  }
  return ret;
};

toolchain.site.util.elapsedSinceWithMillis = function(val) {
  return toolchain.site.util.elapsedSince(val, true);
};
