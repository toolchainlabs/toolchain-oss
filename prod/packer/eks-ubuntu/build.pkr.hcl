# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

build {
  sources = [
    "source.amazon-ebs.ubuntu2004",
  ]

  provisioner "shell" {
    script = "scripts/upgrade_kernel.sh"
    expect_disconnect = true
    pause_before = "90s"
  }

  provisioner "shell" {
    inline = ["mkdir -p /tmp/worker"]
  }

  provisioner "file" {
    source = "files/"
    destination = "/tmp/worker/"
  }

  provisioner "shell" {
    script = "scripts/install-worker.sh"
    environment_vars = [
      "KUBERNETES_VERSION=${local.kubernetes_version}",
      "KUBERNETES_BUILD_DATE=${local.kubernetes_build_date}",
      "BINARY_BUCKET_NAME=${var.binary_bucket_name}",
      "BINARY_BUCKET_REGION=${var.binary_bucket_region}",
      "CNI_PLUGIN_VERSION=${local.cni_plugin_version}",
      "PULL_CNI_FROM_GITHUB=${local.pull_cni_from_github}",
      "AWS_ACCESS_KEY_ID=${var.aws_access_key_id}",
      "AWS_SECRET_ACCESS_KEY=${var.aws_secret_access_key}",
      "AWS_SESSION_TOKEN=${var.aws_session_token}"
    ]
  }

  provisioner "shell" {
    script = "scripts/validate.sh"
  }
}
