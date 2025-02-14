# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "tag_cost_center" {
  type        = string
  description = "A tag to allow calculating cost centers"
  validation {
    condition     = contains(["remoting", "webapp", "dev", "devops"], var.tag_cost_center)
    error_message = "Allowed values are: webapp, remoting, dev, devops."
  }
}
