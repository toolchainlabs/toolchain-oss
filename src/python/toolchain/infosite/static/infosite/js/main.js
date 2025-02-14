// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).
/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

/* COOKIE CONSENT BACKDROP */
function hideDialog () {
  $('.cookie-toast-backdrop').css({
    transition: 'opacity 0.5s',
    opacity: 0
  });
  setTimeout(function() {
    $('.cookie-toast-backdrop').hide()
  }, 1000);
}

function showDialog() {
  var backdrop = $('.cookie-toast-backdrop');
  if (backdrop.length) {
    backdrop.css({
      display: 'block'
    });

    setTimeout(function () {
      $('.cookie-toast-backdrop').css({
        opacity: 1
      })
    }, 1500);
  }
}

function termsAccepted() {
  return $.cookie('accept_terms');
}

function setTermsAccepted() {
  $.cookie('accept_terms', true);
  hideDialog();
}


window.addEventListener("load", function(){
  /* SHOW/HIDE COOKIE CONSENT */
  if (!termsAccepted()) {
    showDialog();
  }
  else {
    hideDialog();
  }

  /* REGISTER ACCEPT BUTTON CLICK EVENT */
  $("#acceptCookieButton").on("click", function () {
    setTermsAccepted();
  });
});

/* Google Analytics  */
window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', 'G-LNX0WQ3C91');