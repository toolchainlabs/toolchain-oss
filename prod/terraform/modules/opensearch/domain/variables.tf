# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "vpc_id" {
  description = "The VPC in which to set up the db."
  type        = string
}

variable "domain_name" {
  description = "The name of the ElasticSearch domain."
  type        = string
}

variable "first_netnum" {
  description = "The ES Domain will own 3 subnets using 3 consecutive netnums starting from this one."
  type        = number
}

variable "access_policies" {
  description = "Acess policy for the ElasticSearch domain."
}

variable "instance_type" {
  description = "Instance type the for ElasticSearch domain nodes."
  default     = "t3.medium.search"
  type        = string
}

variable "instance_count" {
  default     = 2
  description = "Instance count for ElasticSearch domain nodes."
  type        = number
}

variable "extra_tags" {
  description = "Extra tags to apply to resources created by this module"
  type        = map(string)
  default     = {}
}

variable "cognito_options" {
  description = "Conginto options for the ElasticSearch domain (Used for accessing Kibana)."
  type = object({
    enabled          = bool
    user_pool_id     = string
    identity_pool_id = string
    role_arn         = string
  })
  default = {
    enabled          = false
    user_pool_id     = null
    identity_pool_id = null
    role_arn         = null
  }
}

variable "ebs_size" {
  description = "Size (GB) of EBS volume"
  default     = 35
}

variable "ebs_type" {
  description = "EBS Volume type"
  default     = "gp2"
}

variable "public_access" {
  description = "Should the domain subnets be associated with the public internet facing routing table"
  default     = false
}

variable "local_access" {
  description = "Should the domain subnets be associated with the local VPC routing table"
  default     = true
}

variable "az_count" {
  description = "Number of AZ to be used w/ domain (allowed values: 2 or 3)"
  default     = 2
  validation {
    condition     = var.az_count >= 2 && var.az_count <= 3
    error_message = "Allowed values are 2 or 3."
  }
}

variable "custom_domain" {
  description = "custom domain name"
  default     = ""
}

variable "dedicated_master_enabled" {
  description = "enable dedicated master nodes"
  type        = bool
  default     = false
}