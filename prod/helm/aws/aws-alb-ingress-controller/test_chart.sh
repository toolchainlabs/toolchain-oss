#!/usr/bin/env bash
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

helm dependency update prod/helm/aws/aws-alb-ingress-controller
helm template prod/helm/aws/aws-alb-ingress-controller \
     --api-versions monitoring.coreos.com/v1 \
     --kube-version ${K8S_VERSION} --debug \
     --values prod/helm/aws/aws-alb-ingress-controller/fake_values.yaml > dist/aws-alb-ingress-controller-manifests.yaml

yq eval dist/aws-alb-ingress-controller-manifests.yaml
./src/sh/kubernetes/eval_manifest.sh dist/aws-alb-ingress-controller-manifests.yaml