// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).
/*
Copyright 2017 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

var toolchain = toolchain || {};

toolchain.dbz = toolchain.dbz || {};

toolchain.dbz.initBackendsTable = function(selector, dataUrl, explainUrl) {
  function formatCode(val) {
    // See here for this URL munging trick: https://gist.github.com/jlong/2428561.
    var parser = document.createElement('a');
    parser.href = explainUrl;
    parser.search = "sql=" + val;
    return '<a href="' + parser.href + '"><code>' + val + '</code></a>';
  }

  var tableOptions = {
    url: dataUrl,
    showRefresh: true,
    showToggle: true,
    showColumns: true,
    search: true,
    pagination: false,
    sortName: 'state',
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
            title: 'client',
            field: 'client',
            align: 'left',
            valign: 'top',
            class: 'client',
            sortable: true
          },
          {
            title: 'user',
            field: 'usename',
            align: 'left',
            valign: 'top',
            class: 'user',
            sortable: true
          },
          {
            title: 'state',
            field: 'state',
            align: 'left',
            valign: 'top',
            class: 'state',
            sortable: true
          },
          {
            title: 'connected',
            field: 'backend_start',
            align: 'left',
            valign: 'top',
            formatter: toolchain.site.util.elapsedSince,
            class: 'backend_start',
            sortable: true
          },
          {
            title: 'xact start',
            field: 'xact_start',
            align: 'left',
            valign: 'top',
            formatter: toolchain.site.util.elapsedSinceWithMillis,
            class: 'xact_start',
            sortable: true
          },
          {
            title: 'query start',
            field: 'query_start',
            align: 'left',
            valign: 'top',
            formatter: toolchain.site.util.elapsedSinceWithMillis,
            class: 'query_start',
            sortable: true
          },
          {
            title: 'query',
            field: 'query',
            align: 'left',
            valign: 'top',
            class: 'query',
            formatter: formatCode,
            sortable: true
          }
        ]
  };
  toolchain.table.initTable(selector, tableOptions);
};
