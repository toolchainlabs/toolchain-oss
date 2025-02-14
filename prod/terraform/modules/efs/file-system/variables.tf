# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "vpc_id" {
  description = "The VPC in which to set up the db."
  type        = string
}

variable "file_system_name" {
  description = "The name of the file system."
  type        = string
}

variable "k8s_cluster_name" {
  description = "Name of Kubernetes cluster that will use this EFS."
  type        = string
}

variable "availability_zones" {
  description = "A list of availability zones to create mount points on."
  type        = list(string)
}