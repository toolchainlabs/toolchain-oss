#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# A function that returns the name of the user running this script.  Or, to be precise, that user's
# expected name on the bastion host based on ssh config, which is what we take to be the user's
# canonical username, regardless of their `whoami` name on whatever host they're running on.

function get_username() {
  ssh -G bastion.toolchain.private | grep "user " | cut -d' ' -f 2
}
