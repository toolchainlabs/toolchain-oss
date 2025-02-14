// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).
/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

var toolchain = toolchain || {};

toolchain.site = toolchain.site || {};


toolchain.site.setupCsrf = function() {
  // See https://docs.djangoproject.com/en/3.1/ref/csrf/#setting-the-token-on-the-ajax-request
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


toolchain.site.init = function() {
  toolchain.site.setupCsrf();
};
