# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "domain_name" {
  description = "The domain to issue the certificate for."
  type        = string
}

variable "hosted_zone" {
  description = "The hosted zone for the certificate domain."
  type        = string
}

variable "subject_alternative_names" {
  description = "Alternative domain names to associate with the certificate."
  type        = list(string)
  default     = []
}

