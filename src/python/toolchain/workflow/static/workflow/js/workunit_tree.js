// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).
/*
Copyright 2017 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

var toolchain = toolchain || {};

toolchain.workflow = toolchain.workflow || {};

toolchain.workflow.initWorkunitTree = function(selector, dataUrl, rootId) {
  var treeElem = $('#workunit-tree');
  treeElem.jstree({
    core: {
      themes: {
        name: 'proton',
        responsive: true
      },
      data : {
        url : dataUrl,
        data : function(node) {
          return { 'pk' : node.id === '#' ? rootId : node.id };
        }
      }
    }
  });
  treeElem.on('select_node.jstree', function(e, data) {
    window.location.href = data.node.original.status_url;
    return false;
  });
};
