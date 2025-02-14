#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Names of logical dbs to create in a dev db.

export DEPRECATED_DB_NAMES="maven remoting_controller buildgrid_controller"
export DB_NAMES="users buildsense pypi dependency github_integration scm_integration pants_demos oss_metrics payments notifications"
export SIMPLE_DB_NAMES="posthog"
