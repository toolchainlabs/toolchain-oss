# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "name_prefix" {
  description = "The name prefix of the role and instance profile (a dash will be added between the prefix and suffix)."
}

variable "ssh_access" {
  description = "Whether instances with this profile should allow user ssh access."
}
