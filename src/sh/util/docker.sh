#!/usr/bin/env bash
# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

AWS_REGION="us-east-1"
PRIVATE_IMAGE_REGISTRY="283194185447.dkr.ecr.${AWS_REGION}.amazonaws.com/"
PUBLIC_IMAGE_REGISTRY="public.ecr.aws/g2d5g9h4/"

# shellcheck source=src/sh/util/logging.sh
. "$(dirname "${BASH_SOURCE[0]}")/logging.sh"
# shellcheck source=src/sh/util/versions.sh
. "$(dirname "${BASH_SOURCE[0]}")/versions.sh"

function ecr_login_private() {
  debug "Logging in to ECR ${PRIVATE_IMAGE_REGISTRY} ..."
  aws ecr get-login-password | docker login --username AWS --password-stdin ${PRIVATE_IMAGE_REGISTRY}
}

function ecr_login_public() {
  debug "Logging in to ECR ${PUBLIC_IMAGE_REGISTRY} ..."
  # https://docs.aws.amazon.com/AmazonECR/latest/public/public-registries.html#public-registry-auth
  aws ecr-public get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin public.ecr.aws
}

IMAGE_TAG="$(current_tag)"

export PRIVATE_IMAGE_REGISTRY IMAGE_TAG PUBLIC_IMAGE_REGISTRY
