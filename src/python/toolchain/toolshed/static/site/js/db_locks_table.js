// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).
/*
Copyright 2017 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

var toolchain = toolchain || {};

toolchain.dbz = toolchain.dbz || {};

toolchain.dbz.initLocksTable = function(selector, dataUrl) {
  function formatBool(val) {
    var cssClass = val ? 'checkmark' : 'xmark';
    return '<span class="' + cssClass + '"></span>'
  }

  var tableOptions = {
    url: dataUrl,
    showRefresh: true,
    showToggle: true,
    showColumns: true,
    sortName: 'state',
    search: false,
    idField: 'pid',
    rowStyle: function(row) {
      return {
        classes: 'state-' + row.state
      };
    },
    columns:
        [
          {
            title: 'pid',
            field: 'pid',
            align: 'left',
            valign: 'top',
            class: 'pid',
            sortable: true
          },
          {
            title: 'db',
            field: 'datname',
            align: 'left',
            valign: 'top',
            class: 'datname',
            sortable: true
          },
          {
            title: 'type',
            field: 'locktype',
            align: 'left',
            valign: 'top',
            class: 'locktype',
            sortable: true
          },
          {
            title: 'mode',
            field: 'mode',
            align: 'left',
            valign: 'top',
            class: 'mode',
            sortable: true
          },
          {
            title: 'granted',
            field: 'granted',
            align: 'center',
            valign: 'top',
            class: 'granted',
            formatter: formatBool,
            sortable: true
          },
          {
            title: 'relation',
            field: 'relname',
            align: 'left',
            valign: 'top',
            class: 'relname',
            sortable: true
          }
        ]
  };
  toolchain.table.initTable(selector, tableOptions);
};
