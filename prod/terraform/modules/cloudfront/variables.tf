# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "s3_bucket_name" {
  description = "s3 bucket name"
  type        = string
}

variable "s3_path" {
  description = "Path in s3 bucket"
  type        = string
}

variable "access_identity_id" {
  description = "access idenity ID"
  type        = string
}

variable "toolchain_env" {
  description = "Toolchain env tag value"
  type        = string
}

variable "custom_domain_zone" {
  description = "zone under which a custome domain will be created, i.e. assets.my_custom_domain.com"
  type        = string
}

variable "app_name" {
  description = "Application name used with this distrubtion (will be added as a tag)"
  type        = string
}

variable "protected_options" {
  description = "Options for protected data in distribution"
  type = object({
    enabled           = bool
    path_pattern      = string
    cache_policy_id   = string
    trusted_key_group = string
  })
  default = {
    enabled           = false
    path_pattern      = null
    cache_policy_id   = null
    trusted_key_group = null
  }
}
variable "extra_tags" {
  description = "Extra tags to apply to resources created by this module"
  type        = map(string)
  default     = {}
}
