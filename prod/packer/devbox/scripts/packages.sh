#!/bin/bash
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -xeo pipefail

# Upgrade existing packages to obtain security fixes.
sudo apt-get update
sudo apt-get upgrade -y

# Install basic utilities.
# Note: This second `apt-get update` is required to resolve this error (probably due to previous `apt-get upgrade`):
#  Package zip is not available, but is referred to by another package.
#  This may mean that the package is missing, has been obsoleted, or
#  is only available from another source
sudo apt-get update
sudo apt-get install -y \
  bash \
  coreutils \
  curl \
  docker.io \
  gpg \
  graphviz \
  less \
  nvme-cli \
  python3 \
  python3-dev \
  python3-pip \
  python3-venv \
  tar \
  tmux \
  unzip \
  wget \
  zip

# Install build dependnecies.
# Note: Some are pyenv requirements: https://github.com/pyenv/pyenv/wiki/Common-build-problems#prerequisites
sudo apt-get install -y \
  build-essential \
  gcc \
  g++ \
  git \
  libbz2-dev \
  libffi-dev \
  liblzma-dev \
  libncurses5-dev \
  libncursesw5-dev \
  libreadline-dev \
  libsqlite3-dev \
  libssl-dev \
  make \
  openjdk-11-jdk-headless \
  openjdk-11-jre-headless \
  python-openssl \
  tk-dev \
  xz-utils \
  zlib1g-dev \
  postgresql-client \
  postgresql

# Disable containerd and enable Docker.
sudo systemctl stop containerd.service
sudo systemctl disable containerd.service
sudo systemctl enable docker.service
sudo systemctl start docker.service
