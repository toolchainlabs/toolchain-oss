#!/usr/bin/env bash
# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

${__TF_userdata_base}

# docker version known to fix https://aws.amazon.com/security/security-bulletins/AWS-2019-002/.
yum install -y docker-18.06.1ce-7.amzn2

docker_log_config="$(cat <<EOF
{
  "file_path": "/var/log/docker",
  "log_group_name": "/var/log/docker",
  "log_stream_name": "{instance_id}",
  "timestamp_format": "%Y-%m-%dT%H:%M:%S"
}
EOF
)"

add_logfile "$${docker_log_config}"


service docker start
chkconfig docker on
