# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.kubernetes.kubernetes_api import KubernetesAPI


class VolumeAPI(KubernetesAPI):
    def persistent_volume_claim_exists(self, name: str) -> bool:
        """Returns True iff the given persistent volume claim exists in our namespace."""
        try:
            self.api.read_namespaced_persistent_volume_claim_status(name=name, namespace=self.namespace)
            return True
        except self.ApiException as e:
            if e.status == 404:
                return False
            raise
