#!/bin/bash -eux
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Adapted from https://github.com/boxcutter/ubuntu/blob/master/script/vagrant.sh
# Licensed under Apache License Version 2.0

# Disable the release upgrader
echo "==> Disabling the release upgrader"
sed -i.bak 's/^Prompt=.*$/Prompt=never/' /etc/update-manager/release-upgrades

echo "==> Checking version of Ubuntu"
# shellcheck disable=SC1091
. /etc/lsb-release

if [[ $DISTRIB_RELEASE == 16.04 || $DISTRIB_RELEASE == 18.04 ]]; then
    echo "==> Disabling periodic apt upgrades"
    echo 'APT::Periodic::Enable "0";' >> /etc/apt/apt.conf.d/10periodic
fi

echo "==> Updating list of repositories"
# apt-get update does not actually perform updates, it just downloads and indexes the list of packages
apt-get -y update

echo "==> Performing dist-upgrade (all packages and kernel)"
apt-get -y dist-upgrade --force-yes
