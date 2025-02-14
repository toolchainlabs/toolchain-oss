#!/bin/bash
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -xeo pipefail

# Create work directory for software downloads.
WORK_DIR="${HOME}/init-workspace"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

# AWS IAM Authenticator: https://docs.aws.amazon.com/eks/latest/userguide/install-aws-iam-authenticator.html
curl --fail -L -o aws-iam-authenticator https://amazon-eks.s3.us-west-2.amazonaws.com/1.15.10/2020-02-22/bin/linux/amd64/aws-iam-authenticator && \
  echo "fe958eff955bea1499015b45dc53392a33f737630efd841cd574559cc0f41800  aws-iam-authenticator" | sha256sum -c -
sudo mv ./aws-iam-authenticator /usr/local/bin/aws-iam-authenticator
sudo chmod 555 /usr/local/bin/aws-iam-authenticator
sudo chown root.root /usr/local/bin/aws-iam-authenticator

# Keymaker
sudo /usr/bin/pip3 install --upgrade keymaker
sudo /usr/local/bin/keymaker install
# modification of sudoers happens last!
sudo /bin/bash -c "echo '%sudo ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/sudo-init"

# Install udev rules (sourced from Amazon Linux 2) that will automatically label EBS volumes on Nitro
# instances according to the disk name included as vendor data on the NVMe controller identify command.
# These files are initially uploaded by Packer's file provisioner into /tmp as the upload uses a
# non-root user.

sudo mv /tmp/70-ec2-nvme-devices.rules /etc/udev/rules.d/70-ec2-nvme-devices.rules
sudo chown root:root /etc/udev/rules.d/70-ec2-nvme-devices.rules
sudo chmod 444 /etc/udev/rules.d/70-ec2-nvme-devices.rules

sudo mv /tmp/ebsnvme-id /sbin/ebsnvme-id
sudo chown root:root /sbin/ebsnvme-id
sudo chmod 555 /sbin/ebsnvme-id

sudo mv /tmp/ec2nvme-nsid /sbin/ec2nvme-nsid
sudo chown root:root /sbin/ec2nvme-nsid
sudo chmod 555 /sbin/ec2nvme-nsid

# Remove the work directory as the last step.
rm -rf "$WORK_DIR"
