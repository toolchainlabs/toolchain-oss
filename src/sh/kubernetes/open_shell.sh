#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

# Opens a shell on a container in the given dev service in the caller's kubernetes namespace.

if [ $# -lt 1 ]; then
  echo "Usage: $0 <service> (e.g., users, buildsenses/api, crawler/pypi/worker) <container> (defaults to gunicorn)"
  exit 1
fi

k8s_service_name="${1%/}"
k8s_service_name_dashes="${k8s_service_name//\//-}"

pod_name="$(kubectl get pods -l app="${k8s_service_name_dashes}" -o custom-columns=:metadata.name | tail -n 1)"
container="${2:-gunicorn}"
echo "Opening on pod ${pod_name} container ${container}"
kubectl -it exec "$pod_name" --container "${container}" -- /bin/bash
