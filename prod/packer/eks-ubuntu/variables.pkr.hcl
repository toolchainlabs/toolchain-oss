# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# User-configurable variables

variable "worker_disk_size" {
  type = string
  default = "128"
}

variable "kubernetes_version_minor" {
  type = string
  default = "1.19"
}

# Software distribution defaults

variable "binary_bucket_name" {
  type = string
  default = "amazon-eks"
}

variable "binary_bucket_region" {
  type = string
  default = "us-west-2"
}

# AWS credentials for when a private bucket is used

variable "aws_access_key_id" {
  type = string
  default = ""
}

variable "aws_secret_access_key" {
  type = string
  default = ""
}

variable "aws_session_token" {
  type = string
  default = ""
}
