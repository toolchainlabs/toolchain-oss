#!/usr/bin/env bash
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -o pipefail
set -o nounset
set -o errexit

echo ">>> Upgrading kernel."
sudo DEBIAN_FRONTEND=noninteractive apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y linux-aws

echo ">>> Rebooting to pick up upgraded kernel."
sudo reboot
