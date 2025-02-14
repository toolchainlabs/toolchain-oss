#!/bin/bash -eux
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

SSH_USER="${SSH_USERNAME:-vagrant}"
DISK_USAGE_BEFORE_CLEANUP=$(df -h)

# Make sure udev does not block our network - http://6.ptmc.org/?p=164
echo "==> Cleaning up udev rules"
rm -rf /dev/.udev/
rm /lib/udev/rules.d/75-persistent-net-generator.rules

# Blank machine-id (DUID) so machines get unique ID generated on boot.
# https://www.freedesktop.org/software/systemd/man/machine-id.html#Initialization
echo "==> Blanking systemd machine-id"
if [ -f "/etc/machine-id" ]; then
    truncate -s 0 "/etc/machine-id"
fi

# Add delay to prevent "vagrant reload" from failing
echo "pre-up sleep 2" >> /etc/network/interfaces

echo "==> Cleaning up tmp"
rm -rf /tmp/*

# Cleanup apt cache
apt-get -y autoremove --purge
apt-get -y clean
apt-get -y autoclean

echo "==> Installed packages"
dpkg --get-selections | grep -v deinstall

# Remove Bash history
unset HISTFILE
rm -f /root/.bash_history
rm -f "/home/${SSH_USER}/.bash_history"

# Clean up log files
find /var/log -type f | while read -r f; do echo -ne '' > "${f}"; done;

echo "==> Clearing last login information"
: >/var/log/lastlog
: >/var/log/wtmp
: >/var/log/btmp

# Make sure we wait until all the data is written to disk, otherwise
# Packer might quite too early before the large files are deleted
sync

echo "==> Disk usage before cleanup"
echo "${DISK_USAGE_BEFORE_CLEANUP}"

echo "==> Disk usage after cleanup"
df -h
