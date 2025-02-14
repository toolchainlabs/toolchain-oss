# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "aws_region" {
  description = "The aws region name the ssh_cmd will be performed in."
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
