# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

variable "name" {
  description = "The name of the node group."
  type        = string
}

variable "control_plane_state_key" {
  description = "A key suffix for the control plane state, omitting the `state/<region>/` prefix."
  type        = string
}

variable "instance_types" {
  description = "Instance types"
  type        = list(string)
  default     = []
}

variable "instance_category" {
  description = "A category label to apply to the instance, e.g., 'worker' or 'server'."
  type        = string
}

variable "availability_zones" {
  description = "An optional list of specific availability zones to use."
  type        = list(any)
  default     = []
}

variable "key_pair" {
  description = "The name of the key pair to create instances with."
  default     = "toolchain"
  type        = string
}

variable "min_size" {
  description = "Minimum number of instances that must exist."
  type        = number
}

variable "max_size" {
  description = "Maximum number of instances that can exist."
  type        = number
}

variable "desired_capacity" {
  description = "The desired number of instances."
  type        = number
}

variable "can_access_all_dbs" {
  description = "Whether instances can send network traffic to all databases (RDS)."
  type        = bool
  default     = false
}

variable "es_domain_names" {
  description = "ElasticSearch domain names that nodes are allowed to access (for security group config of the instances)."
  type        = list(string)
  default     = []
}

variable "root_volume_size" {
  description = "Size of root EBS volume (in GB)."
  default     = 80
}

variable "extra_security_groups" {
  description = "Extra security groups to apply to the Kubernetes workers' ASG"
  type        = list(string)
  default     = []
}

variable "extra_node_labels" {
  description = "Extra node labels to apply to the Kubernetes workers"
  type        = map(string)
  default     = {}
}

variable "extra_tags" {
  description = "Extra tags to apply to resources created by this module"
  type        = map(string)
  default     = {}
}

variable "cluster_autoscaler_tag" {
  description = "Value for the 'k8s.io/cluster-autoscaler/enabled' tag"
  type        = bool
  default     = false
}

variable "capacity_type" {
  description = "Node group capacity type"
  type        = string
  default     = "ON_DEMAND"
}
