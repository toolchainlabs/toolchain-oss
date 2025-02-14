#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

# Gets a token you can use to log in to the Kubernetes dashboard in a browser.
# Requires your local kubctl config to already grant you admin access to the cluster.
# Will copy the token to your clipboard, unless you're on Linux and don't have xclip
# installed, in which case it'll print the token to stdout.

if [[ $# -eq 1 && ($1 == "-o" || $1 == "--open") ]]; then
  do_open="y"
else
  do_open="n"
fi

if [[ $# -gt 1 || ($# -eq 1 && $do_open == "n") ]]; then
  echo "Usage: $0 [-o|--open]"
  exit 1
fi

# See:  https://kubernetes.io/docs/tasks/access-application-cluster/web-ui-dashboard/#accessing-the-dashboard-ui
clipboard_msg="Token copied to clipboard."
dashboard_url="http://localhost:8001/api/v1/namespaces/kubernetes-dashboard/services/https:kubernetes-dashboard:https/proxy/#/login"

token=$(kubectl create token admin-user -n kubernetes-dashboard)

if [[ $(uname) == 'Darwin' ]]; then
  echo "${token}" | pbcopy
  echo "${clipboard_msg}"
else
  if echo "${token}" | xclip -selection clipboard 2> /dev/null; then
    echo "${clipboard_msg}"
  else
    echo "${token}"
  fi
fi
if ! curl -s --head "${dashboard_url}" > /dev/null; then
  echo "Run \`kubectl proxy\` to create a tunnel to the dashboard service."
fi

echo "Paste the token into the web form at ${dashboard_url}"

if [ "${do_open}" == "y" ]; then
  open "${dashboard_url}"
fi
