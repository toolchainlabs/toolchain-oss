# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "aws_region" {
  description = "The aws region name the ssh_exec will be performed in."
  type        = string
}

variable "ssh_timeout" {
  description = <<DESC
The amount of time to wait for the initial ssh connection / account creation. A string including
units, eg: 5s (5 seconds) or 1m (1 minute).
DESC

  type    = string
  default = "10s"
}

variable "ssh_wait" {
  description = <<DESC
The amount of time to wait between initial connection ssh retries in seconds as an integer.
DESC

  default = 3
}

variable "template_path" {
  description = "The path to the template file to render."
  type        = string
}

variable "ssh_cmd_var" {
  description = "The name for the ssh command template variable; defaults to `__TF_ssh_exec`."
  type        = string
  default     = "__TF_ssh_exec"
}

variable "vars" {
  description = "Template variables to render into the configured template file."
  type        = map(string)
  default     = {}
}
