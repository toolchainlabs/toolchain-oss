# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "vpc_id" {
  description = "The VPC for the load balancer."
}

variable "name" {
  description = "The name of the load balancer."
}

variable "domain" {
  description = "domain name under which to register load balancer"
  type        = string
  default     = "toolchainlabs.com."
}

variable "ports" {
  description = "The ports to listen on and forward to the backends."
  type        = list(number)
}

variable "first_netnum" {
  description = "The load balancer will own 3 public subnets using 3 consecutive netnums starting from this one."
}

variable "access_logs_s3_bucket" {
  description = "The bucket to write access logs to.  If unspecified, will use the general bucket in the region."
  default     = ""
}

variable "access_logs_prefix" {
  description = "The prefix for access log S3 keys (will itself be prefixed with 'elb-access-logs/)'."
}

variable "disable_access_logs" {
  description = "Disable access logs"
  type        = bool
  default     = false
}

variable "extra_tags" {
  description = "Extra tags to apply to resources created by module"
  type        = map(string)
  default     = {}
}
