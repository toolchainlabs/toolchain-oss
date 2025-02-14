# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

output "instance_id" {
  value = aws_instance.cas.id
}

output "private_dns" {
  value = aws_instance.cas.private_dns
}
