#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

# Forwards the appropriate local port to the given dev service in the caller's kubernetes namespace.

if [ $# -lt 1 ]; then
  echo "Usage: $0 <service> (e.g., users, buildsenses/api, crawler/pypi/worker)"
  exit 1
fi

k8s_service_name="${1%/}"
k8s_service_name_dashes="${k8s_service_name//\//-}"

port=$(jq ".services[] | select(.name==\"${k8s_service_name}\") | .dev_port" src/python/toolchain/config/services.json)

cmd="kubectl port-forward --context=dev-e1-1 service/${k8s_service_name_dashes} ${port}:80"
echo "Running ${cmd}"
echo "Access service at http://localhost:${port}"

${cmd}
