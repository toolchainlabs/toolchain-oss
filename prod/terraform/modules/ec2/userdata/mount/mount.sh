# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

mkfs -t ext4 ${VOLUME}
mkdir ${MOUNT_POINT}
mount ${VOLUME} ${MOUNT_POINT}
echo "${VOLUME}  ${MOUNT_POINT} ext4 defaults,nofail 0 2" >> /etc/fstab
