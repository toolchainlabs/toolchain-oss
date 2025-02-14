// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).
/*
Copyright 2017 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

var toolchain = toolchain || {};

toolchain.workflow = toolchain.workflow || {};

toolchain.workflow.initMarkAsFeasible = function(clickTargetSelector, getPks, onSuccess) {
  $(clickTargetSelector).on('click', function(evt) {
    var pks = getPks();
    $.ajax(toolchain.workflow._markSelectedUrl, {
      method: 'POST',
      data: {
        'pks': pks
      },
      success: function(data, textStatus, jqXHR) {
        if (jqXHR.status === 200) {
          $.each(data['new_states'], function(pk, state) {
            $('.work-unit-state-' + pk).html(state);
          });
        }
        if (onSuccess !== undefined) {
          onSuccess();
        }
      }
    });
    evt.preventDefault();
    return false;
  }).mouseup(function() { $(this).blur(); });
};

toolchain.workflow.initMarkAsFeasibleLink = function(clickTargetSelector, pk) {
  toolchain.workflow.initMarkAsFeasible(clickTargetSelector,
      function() { return [pk]; },
      function() { $(clickTargetSelector).hide(); });
};

toolchain.workflow.setMarkSelectedUrl = function(url) {
  toolchain.workflow._markSelectedUrl = url;
};
