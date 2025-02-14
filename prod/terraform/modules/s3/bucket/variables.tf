# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "bucket_name" {
  description = "The name of the s3 bucket. If not provided, we will construct one based on the bucket_name_prefix variable. "
  default     = ""
}

variable "bucket_name_prefix" {
  description = "Prefix for the s3 bucket name (suffix will be <region>.toolchain.com), used only if bucket_name is not specified. Ignored if bucket_name is specified."
}

variable "expiration_lifecycle_policies" {
  description = "object expiration (deletion) lifycycle policies"
  type = map(object({
    enabled = bool
    prefix  = string
    days    = number
  }))
  default = {}
}

variable "extra_tags" {
  description = "Extra tags to apply to resources created by this module"
  type        = map(string)
  default     = {}
}

variable "versioning" {
  description = "Enable versioning of objects in bucket"
  type        = bool
  default     = false
}