// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).
/*
Copyright 2017 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

var toolchain = toolchain || {};

toolchain.dbz = toolchain.dbz || {};

toolchain.dbz.initBlockedLocksTable = function(selector, dataUrl, explainUrl) {
  function formatSQL(val) {
    // See here for this URL munging trick: https://gist.github.com/jlong/2428561.
    var parser = document.createElement('a');
    parser.href = explainUrl;
    parser.search = "sql=" + val;
    return '<a href="' + parser.href + '"><span class="sql">' + val + '</span></a>'
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
        [
          {
            title: 'relation',
            field: 'relname',
            align: 'left',
            valign: 'top',
            class: 'relname',
            rowspan: 2,
            sortable: true
          },
          {
            title: 'blocked',
            align: 'left',
            valign: 'top',
            class: 'pid',
            colspan: 4
          },
          {
            title: 'blocking',
            align: 'left',
            valign: 'top',
            class: 'pid',
            colspan: 4
          }
        ],
        [
          {
            title: 'pid',
            field: 'blocked_pid',
            align: 'left',
            valign: 'top',
            class: 'pid',
            sortable: true
          },
          {
            title: 'type',
            field: 'blocked_locktype',
            align: 'left',
            valign: 'top',
            class: 'locktype',
            sortable: true
          },
          {
            title: 'mode',
            field: 'blocked_mode',
            align: 'left',
            valign: 'top',
            class: 'mode',
            sortable: true
          },
          {
            title: 'statement',
            field: 'blocked_statement',
            align: 'left',
            valign: 'top',
            class: 'statement',
            formatter: formatSQL,
            sortable: true
          },
          {
            title: 'pid',
            field: 'blocking_pid',
            align: 'left',
            valign: 'top',
            class: 'pid',
            sortable: true
          },
          {
            title: 'type',
            field: 'blocking_locktype',
            align: 'left',
            valign: 'top',
            class: 'locktype',
            sortable: true
          },
          {
            title: 'mode',
            field: 'blocking mode',
            align: 'left',
            valign: 'top',
            class: 'mode',
            sortable: true
          },
          {
            title: 'current statement',
            field: 'current_statement_in_blocking_process',
            align: 'left',
            valign: 'top',
            class: 'statement',
            formatter: formatSQL,
            sortable: true
          }
        ]
    ]
  };
  toolchain.table.initTable(selector, tableOptions);
};
