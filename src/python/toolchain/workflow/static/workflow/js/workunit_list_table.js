// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).
/*
Copyright 2017 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

var toolchain = toolchain || {};

toolchain.workflow = toolchain.workflow || {};


toolchain.workflow._getWorkunitStatusLink = function(anchorTxt, url) {
  return '<a href="' + url + '" data-toggle="popover" data-trigger="hover" data-placement="bottom" ' +
         'data-content="' + anchorTxt + '">' + anchorTxt + '</a>'
};

toolchain.workflow.initWorkunitListTable = function(selector, dataUrl, pk, singleton, withLeaseInfo) {
  function workunitStatusLink(val, row) {
    return '<div>' + toolchain.workflow._getWorkunitStatusLink(val, row.status_link) + '</div>';
  }

  function workunitState(val, row) {
    return '<span class="work-unit-state-' + row.pk + '">' + val + '</span>';
  }

  function colorSucceeded(val, row) {
    cls = '';
    if (!moment(row.last_attempt).isSame(moment(0))) {
      cls = (row.last_attempt === row.succeeded_at) ? 'success' : 'warning';
    }
    return {
      classes: cls
    }
  }

  function seconds(val) {
    return '' + val + 's'
  }

  var tableId = selector.startsWith('#') ? selector.substring(1) : selector;
  var customToolbarClass = tableId + '-custom-toolbar';
  $(selector).before(
      '<div class="' + customToolbarClass + '">' +
      '<button class="btn btn-default mark-selected-as-feasible-btn disabled" href="#">Mark as feasible</button>' +
      '</div>');

  var columns = [
    {
      title: 'Selected',
      field: 'selected',
      align: 'left',
      valign: 'middle',
      checkbox: true
    }, {
      title: 'ID',
      field: 'pk',
      align: 'left',
      valign: 'middle',
      sortable: true,
      formatter: workunitStatusLink
    },  {
      title: 'WorkUnit Type',
      field: 'payload_model',
      align: 'left',
      valign: 'middle'
    }, {
      title: 'Description',
      field: 'description',
      align: 'left',
      valign: 'middle',
      formatter: workunitStatusLink,
      cellStyle: { classes: 'workunit-list-table-description' }
    }, {
      title: 'State',
      field: 'state_str',
      align: 'left',
      valign: 'middle',
      formatter: workunitState
    }, {
      title: 'Last attempt',
      field: 'last_attempt',
      align: 'left',
      valign: 'middle',
      sortable: true,
      formatter: toolchain.site.util.shortenDateTime
    }, {
      title: 'Succeeded at',
      field: 'succeeded_at',
      align: 'left',
      valign: 'middle',
      sortable: true,
      formatter: toolchain.site.util.shortenDateTime,
      cellStyle: colorSucceeded
    }];
    if (withLeaseInfo) {
      columns.push({
        title: 'Node',
        field: 'node',
        align: 'left',
        valign: 'middle',
        sortable: true
      });
      columns.push({
        title: 'Lease',
        field: 'leased_remaining',
        align: 'left',
        valign: 'middle',
        sortable: true,
        formatter: seconds
      });
    } else {
      columns.push({
        title: 'Reqs',
        field: 'num_unsatisfied_requirements',
        align: 'left',
        valign: 'middle'
      });
    }

  var tableOptions = {
    url: dataUrl,
    showRefresh: !singleton,
    showToggle: !singleton,
    showColumns: !singleton,
    search: !singleton,
    pagination: !singleton,
    sidePagination: 'server',
    selectItemName: 'selected',
    clickToSelect: true,
    maintainSelected: false,
    toolbarAlign: 'left',
    toolbar: '.' + customToolbarClass,

    idField: 'id',
    columns: columns,
    onPostBody: function() {
      $(selector + ' [data-toggle="popover"]').popover();
    }
  };
  if (pk !== undefined) {
    tableOptions['queryParams'] = function(params) {
      params['pk'] = pk;
      return params;
    };
  }

  toolchain.table.initTable(selector, tableOptions);
  var tableElem = $(selector);
  var markSelectedAsFeasibleBtnSelector = '.' + customToolbarClass + ' .mark-selected-as-feasible-btn';
  function getSelectedPks() {
    return $.map(tableElem.bootstrapTable('getAllSelections'), function(row) { return row.pk; });
  }
  toolchain.workflow.initMarkAsFeasible(markSelectedAsFeasibleBtnSelector, getSelectedPks,
      function() {
        tableElem.bootstrapTable('uncheckAll');
        tableElem.find('tr').removeClass('selected');
        $(markSelectedAsFeasibleBtnSelector).addClass('disabled');
      });

  tableElem.on('check.bs.table uncheck.bs.table', function() {
    $(markSelectedAsFeasibleBtnSelector).toggleClass('disabled', (getSelectedPks().length === 0));
  });
};

toolchain.workflow.initWorkExceptionLogTable = function(selector, dataUrl, workunitPk) {
  function workExceptionDetailLink(val, row) {
    return '<a href="' + row.details_link + '">' + val + '</a>'
  }

  function workunitStatusLink(val, row) {
    return toolchain.workflow._getWorkunitStatusLink(val, row.status_link);
  }

  function workunitState(val, row) {
    return '<span class="work-unit-state-' + row.work_unit_pk + '">' + val + '</span>';
  }

  var inSingleWorkUnit = workunitPk !== undefined;

  var tableId = selector.startsWith('#') ? selector.substring(1) : selector;
  var customToolbarClass = tableId + '-custom-toolbar';
  $(selector).before(
      '<div class="' + customToolbarClass + '">' +
      '<button class="btn btn-default mark-selected-as-feasible-btn disabled" href="#">Mark work unit as feasible</button>' +
      '</div>');

  var tableOptions = {
    url: dataUrl,
    showRefresh: !inSingleWorkUnit,
    showToggle: !inSingleWorkUnit,
    showColumns: !inSingleWorkUnit,
    search: !inSingleWorkUnit,
    pagination: !inSingleWorkUnit,
    sidePagination: 'server',
    selectItemName: 'selected',
    clickToSelect: true,
    maintainSelected: false,
    toolbarAlign: 'left',
    toolbar: '.' + customToolbarClass,

    idField: 'id',
    columns:
        [{
          title: 'Selected',
          field: 'selected',
          align: 'left',
          valign: 'middle',
          checkbox: true
        }, {
          title: 'ID',
          field: 'id',
          align: 'left',
          valign: 'top',
          formatter: workExceptionDetailLink
        }, {
          title: 'Timestamp',
          field: 'timestamp',
          align: 'left',
          valign: 'top',
          sortable: true,
          formatter: toolchain.site.util.shortenDateTime
        }, {
          title: 'Category',
          field: 'category',
          align: 'left',
          valign: 'top'
        }, {
          title: 'Message',
          field: 'message',
          align: 'left',
          valign: 'top',
          formatter: workExceptionDetailLink
        }, {
          title: 'WorkUnit',
          field: 'work_unit',
          align: 'left',
          valign: 'top',
          formatter: workunitStatusLink
        }]
  };
  if (inSingleWorkUnit) {
    tableOptions['queryParams'] = function(params) {
      params['work_unit_pk'] = workunitPk;
      return params;
    };
    // Don't show the WorkUnit column, since we're showing errors in the context of a single WorkUnit.
    tableOptions.columns.pop();
  }
  toolchain.table.initTable(selector, tableOptions);
  var markSelectedAsFeasibleBtnSelector = '.' + customToolbarClass + ' .mark-selected-as-feasible-btn';
  function getSelectedPks() {
    return $.map($(selector).bootstrapTable('getAllSelections'), function(row) { return row.work_unit_pk; });
  }
  toolchain.workflow.initMarkAsFeasible(markSelectedAsFeasibleBtnSelector, getSelectedPks,
      function() {
        $(selector).bootstrapTable('uncheckAll');
        $(selector + ' tr').removeClass('selected');
        $(markSelectedAsFeasibleBtnSelector).addClass('disabled');
      });

  $(selector).on('check.bs.table uncheck.bs.table', function() {
    $(markSelectedAsFeasibleBtnSelector).toggleClass('disabled', (getSelectedPks().length === 0));
  });
};


toolchain.workflow.initWorkunitStatsTable = function(selector, dataUrl, recomputeUrl) {
  var tableId = selector.startsWith('#') ? selector.substring(1) : selector;
  var customToolbarClass = tableId + '-custom-toolbar';
  $(selector).before(
      '<div class="' + customToolbarClass + '">' +
      '<button class="btn btn-default recompute-stats-btn" href="#">Recompute</button>' +
      '</div>');

  function sumCol(rows) {
    var field = this.field;
    return _.sumBy(rows, function(row) { return row[field] || 0; }) || '0';
  }

  var columns = [{
    title: 'WorkUnit Type',
    field: 'ctype__model',
    align: 'left',
    valign: 'top',
    sortable: true,
    footerFormatter: function(rows) { return 'TOTAL'; }
  }];
  ['Pending', 'Ready', 'Leased', 'Succeeded', 'Infeasible'].forEach(function(title) {
    columns.push({
      title: title,
      field: title.toLowerCase(),
      align: 'left',
      valign: 'top',
      sortable: true,
      formatter: function(v) { return v || 0 },
      footerFormatter: sumCol
    });
  });
  var tableOptions = {
    url: dataUrl,
    toolbar: '.' + customToolbarClass,
    showRefresh: true,
    showToggle: false,
    showColumns: true,
    search: false,
    sortName: 'ctype__model',
    pagination: false,
    showFooter: true,
    // For some reason returning classes here doesn't work.
    footerStyle: function(row, idx) { return { css: { 'font-weight': 'bold' } }; },
    columns: columns
  };
  toolchain.table.initTable(selector, tableOptions);
  var recomputeStatsBtnSelector = '.' + customToolbarClass + ' .recompute-stats-btn';
  var btn = $(recomputeStatsBtnSelector);
  btn.on('click', function(evt) {
    btn.addClass('disabled');
    $.ajax({
      method: 'POST',
      url: recomputeUrl,
      data: {},
      always: function(data, textStatus, jqXHR) {
        btn.removeClass('disabled');
      }
    });
    evt.preventDefault();
    return false;
  })
};
