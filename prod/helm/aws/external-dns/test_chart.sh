#!/usr/bin/env bash
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

helm dependency update prod/helm/aws/external-dns
helm template prod/helm/aws/external-dns \
  --api-versions monitoring.coreos.com/v1 \
  --kube-version ${K8S_VERSION} --debug \
  --values prod/helm/aws/external-dns/fake_values.yaml > dist/external-dns-manifests.yaml

yq eval dist/external-dns-manifests.yaml
./src/sh/kubernetes/eval_manifest.sh dist/external-dns-manifests.yaml