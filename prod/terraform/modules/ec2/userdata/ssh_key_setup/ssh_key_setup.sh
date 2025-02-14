# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

echo "Start toolchain ssh_key_setup.sh"

if [ -r /etc/debian_version ]; then
  apt-get update -y
  apt-get install -y python3 python3-pip

  # On Ubuntu 20.04 LTS, EC2 Instance Connect is already configured and enabled in sshd. Uninstall
  # EC2 Instance Connect entirely to disable it.
  apt-get remove -y ec2-instance-connect
  systemctl daemon-reload
else
  yum -y install python3 python3-pip
fi

pip3 install --upgrade keymaker

# Amazon Linux 2 has its own AuthorizedKeysCommand/AuthorizedKeysCommandUser setting, as a placeholder
# for a future feature that appears to be similar to keymaker.
# See https://aws.amazon.com/amazon-linux-2/release-notes/ (search for /opt/aws/bin/curl_authorized_keys).
# When this feature is available, use it instead of keymaker. For now we remove those lines from sshd_config,
# so that keymaker can install its own without conflict.
sed -i /^AuthorizedKeysCommand/d /etc/ssh/sshd_config

export PATH="/usr/local/bin:${PATH}"
/usr/local/bin/keymaker install

echo "%sudo ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/sudo-init

service sshd restart

# An initial call to sync_groups can save minutes waiting for the group assignments to appear.
/usr/local/bin/keymaker sync_groups
