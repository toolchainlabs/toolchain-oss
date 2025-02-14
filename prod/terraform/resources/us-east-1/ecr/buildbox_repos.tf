# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Public repos for buildbox images for Remote execution customers (in the process of being deprecated)

module "toolchain_remote_exec_worker_image" {
  source = "../../../modules/ecr/ecr_repository_private"
  name   = "remoting/worker/toolchainlabs"
}