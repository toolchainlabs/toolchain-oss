# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# A shell script snippet for use in userdata scripts that sets up the CloudWatch agent.

output "script" {
  value = file("${path.module}/cloudwatch_agent.sh")
}
