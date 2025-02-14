#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

# Add Helm plugins.
helm plugin install https://github.com/hypnoglow/helm-s3.git 2> /dev/null || echo "s3 plugin already installed"
helm plugin install https://github.com/databus23/helm-diff --version master 2> /dev/null || echo "diff plugin already installed"
helm plugin install https://github.com/instrumenta/helm-kubeval || echo "kubeeval plugin already installed"

# adding the toolchain repo here since it requires the s3 plugin and AWS credentials to access. so we don't use it in CI (where helm_repos_setup is used).
helm repo add helm-e1 s3://helm.us-east-1.toolchain.com/charts

source ./src/sh/setup/helm_repos_setup.sh

helm repo remove local 2> /dev/null || echo "local repo already removed"
