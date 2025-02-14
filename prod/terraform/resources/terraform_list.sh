#!/usr/bin/env bash
# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euo pipefail

# contains "foo" "${array[@]}" will return 0 iff foo is in the array.
contains() {
  local match="$1"
  shift
  # for without in implicitly iterates over the argument list.
  for element; do [[ "${element}" == "${match}" ]] && return 0; done
  return 1
}

# reverse inarray outarray will place the elements of inarray, in reverse order, in outarray.
reverse() {
  declare -n arr="$1" rev="$2"
  for i in "${arr[@]}"; do
    rev=("${i}" "${rev[@]}")
  done
}

# A helper function to apply the terraform executable within a list of subdirs of the CWD.

# We need two array-typed arguments: the projects and the terraform command args to run on them.
# Bash doesn't let you pass multiple arrays between scripts, but functions inherit their callers'
# local vars. So scripts that use this should set `local TF_PROJECTS=(...)` and then call
# this function with the command args as the function args.
function terraform_list {
  # Projects should be specified in implicit dependency order.
  TF_ALL_CMD="./terraform_all.sh"
  TF_ARGS=("${@}")

  # We must destroy in reverse dependency order.
  # Other cmds are executed in dependency order.
  if contains "destroy" "${TF_ARGS[@]}"; then
    reverse TF_PROJECTS TF_PROJECTS_ORDERED
  else
    TF_PROJECTS_ORDERED=("${TF_PROJECTS[@]}")
  fi

  for project in "${TF_PROJECTS_ORDERED[@]}"; do
    pushd "${project}" > /dev/null
    if [ -e ${TF_ALL_CMD} ]; then
      TF_CMD=${TF_ALL_CMD}
    else
      TF_CMD="terraform"
      echo -e "\n\e[34m** Running '${TF_CMD} ${TF_ARGS[*]}' in ${PWD} **\n"
    fi
    ${TF_CMD} "${TF_ARGS[@]}"
    popd > /dev/null
  done
}
