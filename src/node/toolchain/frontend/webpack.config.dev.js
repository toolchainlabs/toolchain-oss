// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).
/*
Copyright 2019 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { mergeWithCustomize, customizeObject } from 'webpack-merge';
import common from './webpack.config.common.js';

export default mergeWithCustomize({
  customizeObject: customizeObject({
    output: 'replace',
  }),
})(common, {
  mode: 'development',
  devServer: {
    historyApiFallback: true,
    writeToDisk: true,
    inline: false,
  },
});
