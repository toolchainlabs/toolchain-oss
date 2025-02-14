# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "name" {
  description = "The name of the VPC."
  type        = string
}

variable "base_cidr_block" {
  description = "The /12 CIDR block used to generate a /16 block for the VPC."
  type        = string
}

variable "netnum" {
  description = "The 4-bit subnet number to add to the base_cidr_block to create a /16 block for the VPC."
  default     = "" # Defaults to the region number, so default can only be used for one VPC per region.
}

variable "region_numbers" {
  description = "A 4-bit number per region, used to generate the default netnum for the VPC."
  type        = map(any)
  default = {
    us-east-1 = 1
    us-east-2 = 2
    us-west-1 = 3
    us-west-2 = 4
    eu-west-1 = 5
  }
}

variable "availability_zone_index" {
  description = "The index of the availability zone for the general-use public and private subnets."
  default     = "0"
}

variable "vpc_tags" {
  description = "extra tags to apply to the VPC resource"
  type        = map(string)
  default     = {}
}

variable "enable_dynamodb_route" {
  description = "Create an entry in the VPC routing table for routing traffic to dynamodb"
  type        = bool
  default     = false
}

variable "vpn_vpc_name" {
  description = "Name of VPC that has the VPN server (for bastion access) - leave empty for if the VPN is in this VPC"
  type        = string
  default     = ""
}