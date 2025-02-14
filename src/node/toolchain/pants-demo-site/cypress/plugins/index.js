// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).
/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

const injectDevServer = require('@cypress/react/plugins/react-scripts');

module.exports = (on, config) => {
  injectDevServer(on, config);

  return config;
};
