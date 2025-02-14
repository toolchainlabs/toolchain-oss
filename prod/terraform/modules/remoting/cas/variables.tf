# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "availability_zone" {
  description = "Availability Zone where to launch the CAS instance"
  type        = string
}

variable "vpc_id" {
  description = "ID of VPC"
  type        = string
}

variable "cas_volume_id" {
  description = "ID of EBS volume to store CAS data"
  type        = string
}

variable "metadata_volume_id" {
  description = "ID of EBS volume to store metadata"
  type        = string
}