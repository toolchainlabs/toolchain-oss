# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "vpc_id" {
  description = "The VPC in which to set up the db."
}

variable "cluster_name" {
  description = "The name of the Redis Cluster."
}

variable "first_netnum" {
  description = "The cluster will own 3 subnets using 3 consecutive netnums starting from this one."
}

variable "node_type" {
  description = "The node type of the redis nodes (instance size)."
  default     = "cache.t3.micro" # temporary, while we are testing stuff
}

variable "redis_port" {
  description = "redis port"
  default     = 6379
}

variable "description" {
  description = "Description"
  default     = ""
}

variable "number_cache_clusters" {
  description = "Number of cache clusters"
  default     = 1
}

variable "at_rest_encryption" {
  description = "Enable at-rest encryption"
  type        = bool
  default     = true
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
