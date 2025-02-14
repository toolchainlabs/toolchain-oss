# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "vpc_id" {
  description = "The VPC for the cluster."
}

variable "cluster_name" {
  description = "The name of the cluster."
}

variable "first_netnum" {
  description = "The cluster will own 20 subnets using 20 consecutive netnums starting from this one."
}

variable "availability_zones" {
  description = "An optional list of specific availability zones to use."
  type        = list(any)
  default     = []
}

variable "enable_logs" {
  description = "Enable logs"
  type        = bool
  default     = false
}

variable "has_ingress" {
  description = "External access via ingress is enabled for this cluster so configure roles to allow AWS ALB Ingress controller and External-DNS to work"
  type        = bool
  default     = false
}

variable "extra_tags" {
  description = "Extra tags to apply to resources created by this module"
  type        = map(string)
  default     = {}
}

variable "vpn_ingress_secrity_group_id" {
  description = "Security group ID of VPN, will cause the creation of a SG for ingresses that are accessible via VPN."
  type        = string
  default     = ""
}

