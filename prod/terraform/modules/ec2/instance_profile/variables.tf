# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "name" {
  description = "The name of the instance profile and the attached role."
}

variable "ssh_access" {
  description = "Whether instances with this profile should allow user ssh access."
  type        = bool
  default     = false
}

variable "extra_tags" {
  description = "Extra tags to apply to resources created by this module"
  type        = map(string)
  default     = {}
}

variable "managed_policy_arns" {
  description = "Managed AWS IAM policies ARNs to add the IAM role"
  type        = list(string)
  default     = []
}
