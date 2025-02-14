#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

# Add chart repositories. These succeed if repo was already added.
helm repo add eks https://aws.github.io/eks-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add fluent https://fluent.github.io/helm-charts
helm repo add influxdata https://helm.influxdata.com/
helm repo add kubernetes-dashboard https://kubernetes.github.io/dashboard/
helm repo add external-dns https://kubernetes-sigs.github.io/external-dns/
helm repo add aws-efs-csi-driver https://kubernetes-sigs.github.io/aws-efs-csi-driver/
helm repo add autoscaler https://kubernetes.github.io/autoscaler

# Disabled repos since they tend to be falky in CI.
if [[ -z "${CI:-}" ]]; then
  helm repo add bitnami https://charts.bitnami.com/bitnami
  helm repo add jetstack https://charts.jetstack.io
fi
