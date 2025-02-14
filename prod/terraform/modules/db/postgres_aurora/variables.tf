# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "vpc_id" {
  description = "The VPC in which to set up the db."
}

variable "name" {
  description = "The name of the db cluster. Typically the same as the name of the service it's for."
}

variable "first_netnum" {
  description = "The DB will own 3 subnets using 3 consecutive netnums starting from this one."
}

variable "instance_class" {
  description = "The instance class of the db instances."
}

variable "extra_tags" {
  description = "Extra tags to apply to resources created by this module"
  type        = map(string)
  default     = {}
}
