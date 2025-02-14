# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "vpc_id" {
  description = "The VPC for the subnet."
}

variable "name" {
  description = "The name of the subnet."
}

variable "availability_zone" {
  description = "The AZ of the subnet."
}

variable "newbits" {
  description = "The number of bits the subnet adds to the VPC's netmask."
  default     = 8
}

variable "netnum" {
  description = "The fixed value for this subnet in those new bits."
}


variable "map_public_ip" {
  description = "If true, instances in the subnet will receive a public IP on launch."
  default     = false
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
