# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "vpc_id" {
  description = "The VPC in which to set up the cluster."
}

variable "cluster_id" {
  description = "The identifier of the cluster."
}

variable "first_netnum" {
  description = "The cluster will own 3 subnets using consecutive netnums starting from this one."
}

variable "node_type" {
  default     = "dc2.large"
  description = "The redshift node type to use."
}

variable "multi_node" {
  default     = false
  description = "Whether the cluster is single-node or multi-node."
}

variable "s3_copy_buckets" {
  description = "List of buckets that can be the sources of COPY FROM statements in the cluster."
  type        = list(any)
  default     = []
}

# Useful for accessing dev clusters. Should NOT be used for production clusters.
variable "externally_accessible" {
  description = "Whether this cluster can be accessed from the external hosts that are whitelisted for bastion access."
  type        = bool
  default     = false
}

variable "username" {
  description = "The name of the (non-master) user to create."
  default     = "toolchain"
}
