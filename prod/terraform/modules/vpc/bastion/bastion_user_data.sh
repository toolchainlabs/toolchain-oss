#!/bin/bash -xe
# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Template for the "user data" script that EC2 runs on the bastion instance at init time.

${__TF_userdata_base}

# Install useful packages.
rpm -Uvh --replacepkgs https://download.postgresql.org/pub/repos/yum/9.6/redhat/rhel-6-x86_64/pgdg-ami201503-96-9.6-2.noarch.rpm
yum install -y jq postgresql

