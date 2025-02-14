# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "name" {
  description = "The name of the devbox instance."
  type        = string
}

variable "vpc_id" {
  description = "The VPC for the devbox instance."
  type        = string
}

variable "data_volume_id" {
  description = "ID of the EBS volume for the /data mount"
  type        = string
}

variable "key_pair" {
  description = "The name of the key pair for the devbox instance."
  type        = string
  default     = "toolchain"
}

variable "ami_override" {
  description = "Override the AMI to use for the devbox"
  type        = string
  default     = ""
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "c5.xlarge"
}
