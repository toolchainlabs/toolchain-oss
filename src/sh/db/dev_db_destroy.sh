#!/usr/bin/env bash
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Destroys a dev database previously set up on Kubernetes.

# Assumes that the database was created in a kubernetes namespace of the same name.
# Does NOT destroy this namespace.

# Notes:
# - This script deletes all data associated with the database!
# - This script assumes that the user's kubectl points to the appropriate cluster.
# - This script is idempotent and can safely be run multiple times, e.g., to create new logical databases.

source ./src/sh/db/db_names.sh
source ./src/sh/db/dev_db_common.sh

if [ "$NAMESPACE" == "asher" ]; then
  echo "NOT ALLOWRD to destory dev DB in ${NAMESPACE}"
  exit 1
fi

if helm list --namespace "${NAMESPACE}" --kube-context=dev-e1-1 -q | grep -q "${RELEASE_NAME}"; then
  helm delete "${RELEASE_NAME}" --namespace "${NAMESPACE}" --kube-context=dev-e1-1
  echo "Deleted Helm release ${RELEASE_NAME}"
else
  echo "Helm release ${RELEASE_NAME} not found"
fi

pvc_name="data-${RELEASE_NAME}-postgresql-0"

if kubectl get --namespace "${NAMESPACE}" persistentvolumeclaim "${pvc_name}" &> /dev/null; then
  kubectl delete --namespace "${NAMESPACE}" persistentvolumeclaim "${pvc_name}"
else
  echo "PersistentVolumeClaim ${pvc_name} not found"
fi

configmap_name="${RELEASE_NAME}-config"
if kubectl get --namespace "${NAMESPACE}" configmap &> /dev/null; then
  kubectl delete --namespace "${NAMESPACE}" configmap "${configmap_name}"
fi

function delete_secret() {
  secret_name="${RELEASE_NAME}-${1}-creds"
  if kubectl get --namespace "${NAMESPACE}" secret "${secret_name}" &> /dev/null; then
    kubectl delete --namespace "${NAMESPACE}" secret "${secret_name}"
  else
    echo "Secret ${secret_name} not found"
  fi
}

function delete_secret_simple() {
  secret_name="${RELEASE_NAME}-${1}-simple-creds"
  if kubectl get --namespace "${NAMESPACE}" secret "${secret_name}" &> /dev/null; then
    kubectl delete --namespace "${NAMESPACE}" secret "${secret_name}"
  else
    echo "Secret ${secret_name} not found"
  fi
}

delete_secret master

for db_name in ${DB_NAMES}; do
  delete_secret "${db_name}"
done

for db_name in ${DEPRECATED_DB_NAMES}; do
  delete_secret "${db_name}"
done

for db_name in ${SIMPLE_DB_NAMES}; do
  delete_secret_simple "${db_name}"
done
