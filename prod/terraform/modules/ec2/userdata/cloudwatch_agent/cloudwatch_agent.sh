# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

echo "Start toolchain cloudwatch_agent.sh"

if [ -r /etc/debian_version ]; then
  apt-get install -y curl jq
else
  yum install -y curl jq
fi

mkdir /tmp/aws_cloudwatch_agent
cd /tmp/aws_cloudwatch_agent

# TODO: Find a way to pin a specific version of the agent, rather than "latest".
# TODO: Verify package signature here.
if [ -r /etc/debian_version ]; then
  curl -sO https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
  dpkg --install amazon-cloudwatch-agent.deb
else
  curl -sO https://s3.amazonaws.com/amazoncloudwatch-agent/amazon_linux/amd64/latest/amazon-cloudwatch-agent.rpm
  rpm -U ./amazon-cloudwatch-agent.rpm
fi

CW_AGENT_DIR=/opt/aws/amazon-cloudwatch-agent
CW_AGENT_CONF_DIR=${CW_AGENT_DIR}/conf
CW_AGENT_CONF_FILE=${CW_AGENT_CONF_DIR}/agent.conf
CW_AGENT_LOG_FILE=${CW_AGENT_DIR}/logs/amazon-cloudwatch-agent.log
mkdir -p ${CW_AGENT_CONF_DIR}

# This command (re)starts the agent with the latest config.
CW_AGENT_CMD="${CW_AGENT_DIR}/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -c file:${CW_AGENT_CONF_FILE} -s"

cat <<EOF > ${CW_AGENT_CONF_FILE}
{
  "agent": {
    "metrics_collection_interval": 10,
    "logfile": "${CW_AGENT_LOG_FILE}"
  },
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": []
      }
    }
  }
}
EOF

# User data snippets can call this with a stringified array of json objects containing the logfile configs.
function add_logfiles() {
  tmpfile=$(mktemp)
  cat ${CW_AGENT_CONF_FILE} | jq ".logs.logs_collected.files.collect_list += $1" > ${tmpfile}
  mv ${tmpfile} ${CW_AGENT_CONF_FILE}
  ${CW_AGENT_CMD}
}

# User data snippets can call this with a stringified json object containing the logfile config.
function add_logfile() {
  add_logfiles "[$1]"
}


base_log_config="$(cat <<EOF
[
  {
    "file_path": "/var/log/dmesg",
    "log_group_name": "/var/log/dmesg",
    "log_stream_name": "{instance_id}"
  },
  {
    "file_path": "/var/log/messages",
    "log_group_name": "/var/log/messages",
    "log_stream_name": "{instance_id}",
    "timestamp_format": "%b %d %H:%M:%S"
  },
  {
     "file_path": "${CW_AGENT_LOG_FILE}",
     "log_group_name": "amazon-cloudwatch-agent.log",
     "log_stream_name": "{instance_id}",
     "timezone": "UTC"
   }
]
EOF
)"

add_logfiles "${base_log_config}"
