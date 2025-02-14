# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

locals {
  # This map encodes the Kubernetes default versions encoded in the Makefile in the official EKS Packer config.
  # The original Makefile takes these values from the versions described at
  # https://docs.aws.amazon.com/eks/latest/userguide/install-kubectl.html.

  versions_config = {
    "1.18" = {
      "version" = "1.18.8"
      "build_date" = "2020-09-18"
      "pull_cni_from_github" = true
    }
    "1.19" = {
      "version" = "1.19.6"
      "build_date" = "2021-01-05"
      "pull_cni_from_github" = true
    }
  }

  cni_plugin_version = "v0.9.1"

  kubernetes_version = local.versions_config[var.kubernetes_version_minor]["version"]
  kubernetes_build_date = local.versions_config[var.kubernetes_version_minor]["build_date"]
  pull_cni_from_github = local.versions_config[var.kubernetes_version_minor]["pull_cni_from_github"]
}
