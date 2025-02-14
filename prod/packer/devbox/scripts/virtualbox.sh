#!/bin/bash -eux
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Adapted from https://github.com/boxcutter/ubuntu/blob/master/script/virtualbox.sh
# Licensed under Apache License Version 2.0

SSH_USER="${SSH_USERNAME:-vagrant}"

echo "==> Installing VirtualBox guest additions"
apt-get install -y dkms linux-source "linux-headers-$(uname -r)" build-essential perl

VBOX_VERSION="$(cat "/home/${SSH_USER}/.vbox_version")"
mount -o loop "/home/${SSH_USER}/VBoxGuestAdditions_${VBOX_VERSION}.iso" /mnt
sh /mnt/VBoxLinuxAdditions.run
umount /mnt
rm "/home/${SSH_USER}/VBoxGuestAdditions_${VBOX_VERSION}.iso"
rm "/home/${SSH_USER}/.vbox_version"
