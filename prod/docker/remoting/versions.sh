#!/usr/bin/env bash
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Ubuntu 22.04.1 LTS base image https://releases.ubuntu.com/jammy/
# https://hub.docker.com/_/ubuntu/tags
export worker_base_image="ubuntu:jammy-20220801@sha256:42ba2dfce475de1113d55602d40af18415897167d47c2045ec7b6d9746ff148f"

export golang_version=1.18.3
export golang_sha256=956f8507b302ab0bb747613695cdae10af99bbd39a90cae522b7c0302cc27245
