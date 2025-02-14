// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).
/*
Copyright 2019 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

var toolchain = toolchain || {};

toolchain.packagerepopypi = toolchain.packagerepopypi || {};
 

toolchain.packagerepopypi._getProjectLink = function(anchorTxt, url) {
  return '<a href="' + url + '">' + anchorTxt + '</a>'
};

toolchain.packagerepopypi.initProjectListTable = function(selector, dataUrl) {
  function projectLink(val, row) {
    return toolchain.packagerepopypi._getProjectLink(val, row.details_link);
  }

  function pypiLink(val, row) {
    var url = 'https://pypi.org/simple/' + row.name + '/';
    return '<a href="' + url + '">' + url + '</a>';
  }

  var tableId = selector.startsWith('#') ? selector.substring(1) : selector;

  var columns = [
    {
      title: 'Name',
      field: 'name',
      align: 'left',
      valign: 'middle',
      sortable: true,
      class: 'project-name',
      formatter: projectLink
    }, {
      title: 'PyPI URL',
      align: 'left',
      valign: 'middle',
      class: 'pypi-url',
      formatter: pypiLink
    }];

  var tableOptions = {
    url: dataUrl,
    showRefresh: true,
    showToggle: true,
    showColumns: false,
    search: true,
    sortName: 'name',
    pagination: true,
    sidePagination: 'server',
    toolbarAlign: 'left',
    columns: columns
  };

  toolchain.table.initTable(selector, tableOptions);
};
