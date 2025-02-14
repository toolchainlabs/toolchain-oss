#!/usr/bin/env bash
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

# Forwards the service router in dev
./prod/kubernetes/kubectl_setup.sh dev-e1-1
echo "Access dev pants demo site at http://localhost:9050"
kubectl port-forward svc/pants-demos-depgraph-web --namespace=asher --context=dev-e1-1 9050:80
