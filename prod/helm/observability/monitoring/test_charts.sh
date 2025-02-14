#!/usr/bin/env bash
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
mkdir -p dist/
find prod/helm/observability/monitoring/grafana/dashboards -name "*.json"  -print0 | xargs -0 cat  | jq
helm dependency update prod/helm/observability/monitoring/monitoring
helm dependency update prod/helm/observability/monitoring/grafana

helm template prod/helm/observability/monitoring/monitoring \
    --kube-version "${K8S_VERSION}" --debug \
    --values prod/helm/observability/monitoring/monitoring/fake_values.yaml > dist/monitoring_manifests.yaml

yq eval dist/monitoring_manifests.yaml
yq eval 'select(.kind == "Secret").data."alertmanager.yaml"'  dist/monitoring_manifests.yaml | base64 --decode > dist/alert_mgr_cfg.yaml
yq eval dist/alert_mgr_cfg.yaml
amtool check-config dist/alert_mgr_cfg.yaml
helm template prod/helm/observability/monitoring/grafana \
    --kube-version "${K8S_VERSION}" --debug \
    --values prod/helm/observability/monitoring/grafana/fake_values.yaml > dist/grafana_manifests.yaml

# `apiVersion: apiregistration.k8s.io/v1beta1 kind: APIService` is not avaibale in the upsream schema repos. so we ignore it for now.
./src/sh/kubernetes/eval_manifest.sh -skip APIService dist/monitoring_manifests.yaml 
./src/sh/kubernetes/eval_manifest.sh dist/grafana_manifests.yaml