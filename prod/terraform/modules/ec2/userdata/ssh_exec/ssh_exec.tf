# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Renders a template file with `../ssh_cmd` machinery inserted in the `__TF_ssh_exec` template
# variable by default.

module "ssh_cmd" {
  source = "../ssh_cmd"

  aws_region  = var.aws_region
  ssh_timeout = var.ssh_timeout
  ssh_wait    = var.ssh_wait
}

locals {
  script_contents = templatefile(var.template_path, merge(map(var.ssh_cmd_var, module.ssh_cmd.script), var.vars))
}

resource "local_file" "ssh_exec" {
  filename = "${path.module}/.generated/${basename(var.template_path)}"
  content  = local.script_contents
}

# The rendered contents of the template file.
output "rendered" {
  value = local.script_contents
}

# The rendered script's path. This script will be executable and thus usable as a `local_exec`
# `command`.
output "filename" {
  value = local_file.ssh_exec.filename
}
