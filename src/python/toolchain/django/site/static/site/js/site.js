// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).
/*
Copyright 2017 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

var toolchain = toolchain || {};

toolchain.site = toolchain.site || {};

toolchain.site.setupNavBar = function() {
  // Set the active nav before reload, so the user sees immediate feedback.
  $('.nav a').on('click', function() {
    $('.nav').find('.active').removeClass('active');
    $(this).parent().addClass('active');
  });

  // Set the active nav after reload.
  var activeNavId = '#nav-' + window.location.pathname.split('/', 2)[1];
  $(activeNavId).addClass('active');
};

toolchain.site.setupCsrf = function() {
  // See https://docs.djangoproject.com/en/1.11/ref/csrf/#setting-the-token-on-the-ajax-request
  function csrfSafeMethod(method) {
    // these HTTP methods do not require CSRF protection.
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
  }
  var csrftoken = $('[name=csrfmiddlewaretoken]').val();
  $.ajaxSetup({
    beforeSend: function(xhr, settings) {
      if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
        xhr.setRequestHeader('X-CSRFToken', csrftoken);
      }
    }
  });
};

toolchain.site.setLabelsAsPlaceholders = function() {
  // Copied from https://gist.github.com/makeusabrew/985739.
  $('form :input.label-as-placeholder').each(function (index, elem) {
    var eId = $(elem).attr('id');
    var label = null;
    if (eId && (label = $(elem).parents('form').find('label[for=' + eId + ']')).length === 1) {
      if (!$(elem).attr('placeholder')) {
        $(elem).attr('placeholder', $(label).html());
      }
    }
  });
};

toolchain.site.init = function() {
  toolchain.site.setupNavBar();
  toolchain.site.setupCsrf();
  toolchain.site.setLabelsAsPlaceholders();
};
