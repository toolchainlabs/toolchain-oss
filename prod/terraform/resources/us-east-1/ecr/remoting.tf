# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

module "proxy_server_repository" {
  source = "../../../modules/ecr/ecr_repository_private"
  name   = "remoting/proxy_server"
}

module "storage_server_repository" {
  source = "../../../modules/ecr/ecr_repository_private"
  name   = "remoting/storage_server"
}
