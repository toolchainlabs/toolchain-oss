#!/usr/bin/env bash
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

# Forwards the service router in dev
./prod/kubernetes/kubectl_setup.sh dev-e1-1
echo "Access dev service router at http://localhost:9500"
kubectl port-forward svc/servicerouter --namespace=asher --context=dev-e1-1 9500:80
