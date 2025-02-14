# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "user_pool_name" {
  description = "User pool name"
  default     = "Toolchain-GoogleAuth"

}

variable "identity_pool_name" {
  description = "appliction name"
}

variable "authenticated_role_name" {
  description = "Authenticated role name"
}


variable "unauthenticated_role_name" {
  description = "Unauthenticated role name"
}
variable "es_domain_name" {
  description = "ES Domain name"
}

variable "client_id" {
  description = "The application client ID in the user pool"
}