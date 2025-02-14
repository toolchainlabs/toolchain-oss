// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).
/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import path from 'path';
import { mergeWithCustomize, customizeObject } from 'webpack-merge';
import HtmlWebpackPlugin from 'html-webpack-plugin';
import common from './webpack.config.common.js';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default mergeWithCustomize({
  customizeObject: customizeObject({
    output: 'replace',
  }),
})(common, {
  mode: 'development',
  output: {
    publicPath: '/',
  },
  devServer: {
    proxy: {
      '/api': 'http://localhost:9500',
      '/auth': 'http://localhost:9500',
    },
    hot: true,
    historyApiFallback: true,
  },
  plugins: [
    new HtmlWebpackPlugin({
      title: 'Toolchain (development)',
      template: path.resolve(__dirname, 'dev-only-index.html'),
      hash: true,
      appInitData: Buffer.from(
        JSON.stringify({
          host: 'http://localhost:8080/',
          sentry: null,
          flags: null,
          impersonation: null,
          support_link: 'random.toolchain',
          assets: {
            version: 'local-development',
            disableVersionCheck: true,
          },
        })
      ).toString('base64'),
    }),
  ],
});
