#!/usr/bin/env bash
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
cd prod/packer/eks-ubuntu

# Files vendored from the official AWS EKS AMI at https://github.com/awslabs/amazon-eks-ami.
VENDORED_FILES=(
  bootstrap.sh
  docker-daemon.json
  eni-max-pods.txt
  iptables-restore.service
  kubelet-config.json
  kubelet-kubeconfig
  kubelet.service
  logrotate-kube-proxy
  logrotate.conf
)

# Download the latest copies of the vendored files.
for f in "${VENDORED_FILES[@]}" ; do
  curl --fail -L -o "files/${f}" "https://raw.githubusercontent.com/awslabs/amazon-eks-ami/master/files/${f}"
done
