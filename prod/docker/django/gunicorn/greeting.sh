# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

if [[ "$TOOLCHAIN_ENV" == "toolchain_dev" ]]; then
    echo "shell running in DEV environment for ${K8S_POD_NAMESPACE}"
    echo "Kubernetes namespace: ${K8S_POD_NAMESPACE} pod: ${K8S_POD_NAME}"
elif [[ "$TOOLCHAIN_ENV" == "toolchain_prod" ]]; then
    echo "********************************************************************"
    echo "*****       API SERVICE PROD ENV - BE EXTREMELY CAREFUL        ******"
    echo "********************************************************************"
    echo "Kubernetes namespace: ${K8S_POD_NAMESPACE} pod: ${K8S_POD_NAME}"
else
    echo "Unknown environment, TOOLCHAIN_ENV is not defined"
    echo "Kubernetes namespace: ${K8S_POD_NAMESPACE} pod: ${K8S_POD_NAME}"
fi
