// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).
/*
Copyright 2017 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

var toolchain = toolchain || {};
toolchain.packagerepo = toolchain.packagerepo || {};
toolchain.packagerepo.maven = toolchain.packagerepo.maven || {};

// tpl should be a url in which XXXXX should be substituted for row.group_id.
toolchain.packagerepo.maven.setGroupLinkTemplate = function(tpl) {
  toolchain.packagerepo.maven._groupLinkTemplate = tpl;
};

toolchain.packagerepo.maven.initGroupListTable = function(selector, dataUrl) {
  function detailsLink(val, row) {
    if (toolchain.packagerepo.maven._groupLinkTemplate) {
      var url = toolchain.packagerepo.maven._groupLinkTemplate.replace('XXXXX', row.group_id);
      return '<a href="' + url + '">' + val + '</a>'
    }
    return val;
  }

  var tableOptions = {
    url: dataUrl,
    showRefresh: true,
    showToggle: false,
    showColumns: false,
    search: true,
    pagination: true,
    sidePagination: 'server',

    idField: 'group_id',
    columns:
        [
          {
            title: 'Group ID',
            field: 'group_id',
            align: 'left',
            valign: 'middle',
            formatter: detailsLink
          }
        ]
  };
  toolchain.table.initTable(selector, tableOptions);
};
