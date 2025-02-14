#!/usr/bin/env bash
# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

mkdir -p "${HOME}/.cache/kubeconform"

kubeconform -output tap -strict -debug \
  -kubernetes-version "${K8S_VERSION}.0" \
  -schema-location default \
  -schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json' \
  -cache "${HOME}/.cache/kubeconform" \
  "$@"
