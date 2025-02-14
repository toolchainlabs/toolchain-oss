# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# A sourceable bash snippet that supports executing commands on toolchainlabs EC2 instances
# provisioned with ec2/userdata/ssh_key_setup. This handles initial login, which requires connecting
# once and hanging up to allow `keymaker` to create a user account on the fly.

TIMEOUT_CMD="$$(
  which gtimeout || which timeout || \
  (echo >&2 'Please install `timeout`. On OSX you can run: ./src/sh/setup/homebrew.sh' && exit 1)
)"

# This snippet is used for terraforming and in that context we can easily rotate through subnets
# and encounter host key changed scenarios. We want provisioning to proceed; so we use a throwaway
# known hosts file to avoid key change scenarios in the automation pipeline.
TEMP_KNOWN_HOSTS="$$(mktemp -t known_hosts.XXXXX)"
trap "rm -f $${TEMP_KNOWN_HOSTS}" EXIT

SSH_OPTS=(
  -o ProxyJump=${bastion_host}
  -o StrictHostKeyChecking=no
  -o UserKnownHostsFile=$${TEMP_KNOWN_HOSTS}
)

# A convenience that allows generated scripts to be tested from the command line interactively.
function get_target_host() {
  read -p "Please supply the host to execute $$0 against: " target_host
  if [ -n "$${target_host}" ]; then
    echo "$${target_host}"
  else
    echo >&2 "Cannot run without a TARGET_HOST."
    exit 1
  fi
}

TARGET_HOST=$${TARGET_HOST:-$${1:-$(get_target_host)}}

SSH_CMD="ssh $${SSH_OPTS[@]} $${TARGET_HOST}"

function ssh_cmd() {
  $${SSH_CMD} "$$@"
}

function scp_cmd() {
  local -r from="$$1"
  local -r to="$$2"

  scp "$${SSH_OPTS[@]}" "$${from}" "$${TARGET_HOST}:$${to}"
}

# Get past initial login account creation by `keymaker` before handing control to the sourcing
# script, which can then use scp_cmd and ssh_cmd to perform file transfer and remote command
# execution on the TARGET_HOST.
until "$${TIMEOUT_CMD}" -s KILL -v ${ssh_timeout} $${SSH_CMD} "$${SSH_TEST:-true}"; do
  sleep ${ssh_wait}
done