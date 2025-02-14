# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# A shell script snippet for use in userdata scripts, with basic functionality we want on all boxes.


# The SSH key setup script.
module "ssh_key_setup" {
  source = "../ssh_key_setup"
}

# The CloudWatch agent setup script.
module "cloudwatch_agent" {
  source = "../cloudwatch_agent"
}

locals {
  base_script = join("\n", [
    module.ssh_key_setup.script,
    module.cloudwatch_agent.script
  ])
}

output "script" {
  value = local.base_script
}
