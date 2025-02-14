# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "vpc_id" {
  description = "The VPC in which to set up the db."
}

variable "base_cluster_name" {
  description = "The base name for Redis clusters defined by this module."
}

variable "shard_config" {
  description = "Configuration of each shard cluster."
  type = map(object({
    az        = string,
    node_type = string,
  }))
}

variable "first_netnum" {
  description = "The cluster will own subnets using consecutive netnums starting from this one for each AZ."
}

variable "availability_zones" {
  description = "Availability zones to make available for use by cache nodes."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "redis_port" {
  description = "redis port"
  default     = 6379
}

variable "description" {
  description = "Description"
  default     = ""
}

variable "param_group_name" {
  description = "Parameters group name"
  default     = "default.redis6.x"
}

variable "extra_tags" {
  description = "Extra tags to apply to resources created by this module"
  type        = map(string)
  default     = {}
}
