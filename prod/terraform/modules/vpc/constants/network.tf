# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# CIDR block for the main VPC in a region.
output "main_vpc_cidr_block" {
  value = "10.0.0.0/12"
}

# CIDR block for the remoting VPC in a region.
# Note that this CIDR block is incremented by one in the network portion (which is bit 5 because of the /12).
output "remoting_vpc_cidr_block" {
  value = "10.16.0.0/12"
}
