// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).
/*
Copyright 2017 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

var toolchain = toolchain || {};

toolchain.table = toolchain.table || {};


toolchain.table.initTable = function(selector, tableOptions, autoRefreshInterval) {
  // Id for the purpose of storing state for this table in the fragment.
  // Cannot start with a # because that confuses the fragment-setting code.
  var tableId = selector.startsWith('#') ? selector.substring(1) : selector;

  var tableElem = $(selector);

  function parseTableStatesFromFragment() {
    var ret = {};
    // Note that window.location.hash includes the leading # when reading it.
    var tableStateStrs = window.location.hash.substring(1).split(',');
    $.each(tableStateStrs, function(_, ts) {
      if (ts === '') {
        return;
      }
      var tsParts = ts.split('!', 2);
      var tid = tsParts[0];
      var state = {};
      var keyValStrs = tsParts[1].split('&');
      $.each(keyValStrs, function(_, kvStr) {
        var kv = kvStr.split('=');
        state[kv[0]] = kv[1];
      });
      ret[tid] = state;
    });
    return ret;
  }

  function setTableStatesOnFragment(states) {
    var tableStateStrs = [];
    $.each(states, function(id, st) {
      var keyValStrs = [];
      $.each(st, function(k, v) {
        keyValStrs.push('' + k + '=' + v);
      });
      tableStateStrs.push('' + id + '!' + keyValStrs.join('&'));
    });
    history.replaceState(null, '', '#' + tableStateStrs.join(','));
  }

  function updateTableStateOnFragment(update) {
    var states = parseTableStatesFromFragment();
    var state = states[tableId] || {};
    $.each(update, function(key, val) {
      state[key] = val;
    });
    states[tableId] = state;
    setTableStatesOnFragment(states);
  }

  var tableState = parseTableStatesFromFragment()[tableId];
  function getFromState(name, dflt) {
    if (tableState && tableState.hasOwnProperty(name)) {
      return tableState[name];
    }
    return dflt;
  }

  var tableOptionsFromState = {
    sortName: getFromState('sort'),
    sortOrder: getFromState('order'),
    pageNumber: parseInt(getFromState('pageNumber', '1')),
    pageSize: parseInt(getFromState('pageSize', '100')),
    searchText: getFromState('searchText'),
    cardView: getFromState('cardView') === 'true'
  };
  var fullTableOptions = $.extend({}, tableOptions, tableOptionsFromState);

  tableElem.bootstrapTable(fullTableOptions);

  tableElem.on('sort.bs.table', function(evt, sort, order) {
    updateTableStateOnFragment({sort: sort, order: order });
  }).on('search.bs.table', function(evt, text) {
    updateTableStateOnFragment({searchText: text});
  }).on('page-change.bs.table', function(evt, number, size) {
    updateTableStateOnFragment({pageNumber: number, pageSize: size});
  }).on('toggle.bs.table', function(evt, cardView) {
    updateTableStateOnFragment({cardView: cardView});
  });

  if (autoRefreshInterval) {
    setInterval(function() { tableElem.bootstrapTable('refresh') }, autoRefreshInterval);
  }

  // Set up range-selection.
  function processRange(a, b, state) {
    // We don't know which of a, b comes first, so just turn on checking when we encounter
    // one of them, and off when we encounter the other.
    if (a === b) {
      return;
    }
    document.getSelection().removeAllRanges();  // Clear the browser's unintended text-selection.
    var inRange = false;
    _.forEach(tableElem.bootstrapTable('getData', true), function(elem, idx) {
      if (elem.id === a || elem.id === b) {
        inRange = !inRange;
        if (!inRange) {
          return false;  // Short-circuit.
        }
      }
      if (inRange) {
        tableElem.bootstrapTable(state ? 'check' : 'uncheck', idx);
      }
    });
  }

  $(':root').on('keydown', function(e) { if (e.key === 'Shift') { tableElem.data('shift', true); } })
      .on('keyup'  , function(e) { if (e.key === 'Shift') { tableElem.data('shift', false); } });

  tableElem.on('click-row.bs.table', function(e, row) {
    var prevClickedRow = tableElem.data('prevClickedRow');
    var curRowSelected = !!row.selected;
    var prevRowSelected = prevClickedRow ? prevClickedRow.selected : false;
    if (tableElem.data('shift') && prevClickedRow && curRowSelected === prevRowSelected) {
      processRange(prevClickedRow.id, row.id, !row.selected);
      tableElem.data('prevClickedRow', null);
    } else {
      // Note: Can't use row itself as the data, because its selected field is mutable.
      tableElem.data('prevClickedRow', {
        id: row.id,
        selected: curRowSelected
      });
    }
  });
};
