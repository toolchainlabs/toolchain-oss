# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "vpc_id" {
  description = "The VPC for the load balancer."
}

variable "name" {
  description = "The name of the load balancer."
}

variable "first_netnum" {
  description = "The load balancer will own 3 public subnets using 3 consecutive netnums starting from this one."
}

variable "access_logs_s3_bucket" {
  description = "The bucket to write access logs to.  If unspecified, will use the logs bucket in the region."
  default     = ""
}

variable "access_logs_prefix" {
  description = "The prefix for access log S3 keys (will itself be prefixed with 'elb-access-logs/)'."
}

variable "extra_security_groups" {
  description = "Extra security groups to enroll the alb in."
  type        = list(any)
  default     = []
}

variable "enable_http" {
  description = "Enable an HTTP listener."
  default     = true
}

variable "enable_https" {
  description = "Enable an HTTPS listener."
  default     = true
}
