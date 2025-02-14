# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Provides user_data for a non-ECS host that will run the docker daemon.

module "userdata_base" {
  source = "../../userdata/base"
}


output "rendered" {
  value = templatefile("${path.module}/user_data.sh", {
    __TF_userdata_base = module.userdata_base.script
  })
}
