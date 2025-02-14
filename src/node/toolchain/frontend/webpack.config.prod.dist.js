// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).
/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import webpack from 'webpack';
import { merge } from 'webpack-merge';
import { BundleAnalyzerPlugin } from 'webpack-bundle-analyzer';
import fs from 'fs';
import path from 'path';
import common from './webpack.config.common.js';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const distPath = path.resolve(__dirname, '..', '..', '..', '..', 'dist');
const serviceRouterDist = path.resolve(distPath, 'spa', 'servicerouter', 'generated');
const bundleReportPath = path.resolve(distPath, 'bundle-report.html');

export default merge(common, {
  mode: 'production',
  devtool: 'source-map',
  output: {
    filename: '[name].js',
    path: serviceRouterDist,
  },
  plugins: [
    new webpack.BannerPlugin({ banner: fs.readFileSync(path.resolve(__dirname, 'COPYRIGHT'), 'utf8'), raw: true }),
    new BundleAnalyzerPlugin({ openAnalyzer: false, reportFilename: bundleReportPath, analyzerMode: 'static' }),
  ],
});
