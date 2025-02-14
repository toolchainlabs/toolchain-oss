# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "service_name" {
  description = "canonical name of service"
  type        = string
}

variable "service_description" {
  description = "service description"
  type        = string
}

variable "schedule_name" {
  description = "Name of schedule to use in service esclation policy."
  type        = string
}
