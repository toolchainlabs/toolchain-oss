#!/usr/bin/env bash
# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# a script to build and push the nginx image shared by all django deploys.
# This is the nginx that fronts gunicorn for serving dynamic views, and directly serves static files.
# This image is reusable across all django services. There is typically no need to build and push
# it when creating a new Django-based service or updating an existing one.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

source ./src/sh/util/logging.sh
source ./src/sh/util/docker.sh

# Login into AWS Public ECR repo.
aws ecr-public get-login-password --region us-east-1 | docker login --username AWS --password-stdin public.ecr.aws

NGINX_INTERNAL_REMOTE_TAG="${PRIVATE_IMAGE_REGISTRY:-}django/nginx-internal:${IMAGE_TAG:-dev}"
NGINX_EDGE_REMOTE_TAG="${PRIVATE_IMAGE_REGISTRY:-}django/nginx-edge:${IMAGE_TAG:-dev}"


debug "Building and pushing django nginx images at rev ${IMAGE_TAG:-dev} ..."

debug "Building nginx images ..."

docker build --platform=linux/amd64 --file=prod/docker/django/nginx/Dockerfile.internal prod/docker/django/nginx --tag ${NGINX_INTERNAL_REMOTE_TAG}
docker build --platform=linux/amd64 --file=prod/docker/django/nginx/Dockerfile.edge prod/docker/django/nginx --tag ${NGINX_EDGE_REMOTE_TAG}


ecr_login_private

debug "Pushing django nginx images ..."
docker push ${NGINX_INTERNAL_REMOTE_TAG}
docker push ${NGINX_EDGE_REMOTE_TAG}

info "Published new images to ${NGINX_INTERNAL_REMOTE_TAG} ${NGINX_EDGE_REMOTE_TAG} "
