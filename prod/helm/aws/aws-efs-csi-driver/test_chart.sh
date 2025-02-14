#!/usr/bin/env bash
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

helm dependency update prod/helm/aws/aws-efs-csi-driver
helm template prod/helm/aws/aws-efs-csi-driver \
    --kube-version "${K8S_VERSION}" --debug \
    --values prod/helm/aws/aws-efs-csi-driver/fake_values.yaml > dist/aws-efs-csi-driver-manifests.yaml

yq eval dist/aws-efs-csi-driver-manifests.yaml
./src/sh/kubernetes/eval_manifest.sh dist/aws-efs-csi-driver-manifests.yaml