# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# A shell script snippet for use in userdata scripts, that mounts a volume.


output "script" {
  value = templatefile("${path.module}/mount.sh", {
    VOLUME      = var.volume
    MOUNT_POINT = var.mount_point
  })

}
