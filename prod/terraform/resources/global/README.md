# Terraform configuration - global

Terraform configuration for global entities that exist once in all of AWS.

This currently means IAM resources (roles, policies and instance profiles), as those
are not tied to any region and can be reused globally.

The individual files are fairly self-explanatory (assuming understanding of the underlying AWS concepts).
