# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# A shell script snippet for use in userdata scripts, that sets up SSH key fetching.

output "script" {
  value = file("${path.module}/ssh_key_setup.sh")
}
