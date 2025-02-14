// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).
window.addEventListener('load', function() {
  document.getElementById('try-again').addEventListener('click', function(e) {
      e.preventDefault();
      goBack();
  })
})

function goBack() {
  window.history.back();
};