# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "vpc_id" {
  description = "The VPC in which to set up the lambda."
  type        = string
}

variable "function_name" {
  description = "Name of the lambda function."
  type        = string
}

variable "first_netnum" {
  description = "The netnums for the lambda function subnets."
  type        = number
}

variable "security_group_name" {
  description = "Name of security group to be associated with lambda function."
  type        = string
}

variable "environment_variables" {
  description = "Envionment variables to assicate with lambda function."
  type        = map(string)
}

variable "extra_policies_arns" {
  description = "Extra policies ARNs to attach to the lambda function's IAM role."

  type    = list(string)
  default = []
}

variable "s3_key" {
  description = "s3 key path that contains the zip file with the lambda function code."
  type        = string
}

variable "extra_tags" {
  description = "Extra tags to apply to resources created by this module"
  type        = map(string)
  default     = {}
}

variable "timeout" {
  description = "Lambda function execution timeout in seconds."
  default     = 14
  type        = number
}