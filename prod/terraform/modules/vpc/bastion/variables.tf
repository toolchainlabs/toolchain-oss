# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "vpc_name" {
  description = "The name of the VPC for the bastion."
  type        = string
}

variable "key_pair" {
  description = "The name of the key pair for the bastion host."
  default     = "toolchain"
  type        = string
}

variable "availability_zone_index" {
  description = "The index of the availability zone for the bastion host. We support only one bastion per AZ."
  default     = "0"
}

variable "extra_security_groups" {
  description = "Extra security groups to apply to the bastion host"
  type        = list(string)
  default     = []
}

variable "env_name" {
  description = "Environment name to add to DNS name"
  type        = string
  default     = ""
}

variable "extra_tags" {
  description = "Extra tags to apply to bastion resources"
  type        = map(string)
  default     = {}
}
