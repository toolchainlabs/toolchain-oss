# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).
# Copyright 2019-2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Make build images for dependencies available below.
ARG worker_base_image

FROM ${worker_base_image}
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies of the Toolchain executor.
RUN apt-get update && \
    apt-get install -y \
      libfuse3-3 \
      libgrpc++1 \
      libprotobuf23 \
      fuse3 \
      rsync && \
    apt-get -y clean

# Create toolchain user that the utility will run as.
RUN mkdir -p /toolchain && \
  adduser \
    --disabled-password \
    --disabled-login \
    --no-create-home \
    --uid 1000 \
    --home /toolchain \
    --shell /bin/false \
    --gecos 'Toolchain Worker' \
      toolchain

COPY --chown=root:root ./fuse.conf /etc/fuse.conf

RUN chown toolchain:toolchain /toolchain && chmod 755 /toolchain
USER toolchain:toolchain
WORKDIR /toolchain
