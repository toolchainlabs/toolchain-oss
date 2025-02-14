#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Our pods (which run on the default serviceaccount unless otherwise specified) do not (typically)
# need access to the API server, so they do not need the serviceaccount's token.
# See page 43 of https://kubernetes-security.info/.
# Pods that do need such access should run on dedicated serviceaccounts with appropriate role bindings.
kubectl patch serviceaccount default -p $'automountServiceAccountToken: false'
