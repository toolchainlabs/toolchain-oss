#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# A script to copy a secret from AWS secrets manager into a Kubernetes Secret resource.

if (( $# != 1 )); then
  echo "Usage: aws_secret_to_k8s_secret.sh aws-secret-name"
  exit 1
fi

secret_name="$1"

secret_string_raw=$(aws secretsmanager get-secret-value --secret-id "${secret_name}" | jq -r .SecretString)
secret_string_encoded=$(echo "${secret_string_raw}" | base64)

cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: ${secret_name}
type: Opaque
data:
  secret_string: ${secret_string_encoded}
EOF
