# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "cardinality" {
  description = "How many adjacent subnets to create."
  type        = number
  default     = 1
}

variable "availability_zones" {
  description = "An optional list of specific availability zones to use."
  type        = list(any)
  default     = []
}

variable "vpc_id" {
  description = "The VPC for the subnets."
}

variable "name" {
  description = "If one subnet, its name. Otherwise each subnet's name is this string with an ordinal appended."
}

variable "newbits" {
  description = "The number of bits each subnet adds to the VPC's netmask."
  default     = 8
}

variable "first_netnum" {
  description = "The first of the consecutive fixed values for each subnet in those new bits."
}

variable "map_public_ip" {
  description = "If true, instances in each subnet will receive a public IP on launch."
  default     = false
}

variable "tags" {
  description = "Key-value mappings to tag the subnets with. The Name tag will be overwritten if provided."
  type        = map(any)
  default     = {}
}

variable "public_route_table_id" {
  description = "ID of the public route table for this VPC"
  type        = string
  default     = ""
}

variable "nat_route_table_id" {
  description = "ID of the NAT route table for this VPC"
  type        = string
  default     = ""
}

variable "local_route_table_id" {
  description = "ID of the local route table for this VPC"
  type        = string
  default     = ""
}
