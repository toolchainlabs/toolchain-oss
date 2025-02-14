# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from colors import cyan, green, red

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.util.leveldb.latest import latest_ordinal
from toolchain.util.leveldb.urls import copy_leveldb_and_input_list


def ensure_local_leveldb(local_base_dir_parent: str, remote_base_dir_parent: str, name: str) -> str:
    local_base_dir = f"{local_base_dir_parent}{name}/"
    remote_base_dir = f"{remote_base_dir_parent}{name}/"
    latest_local_ordinal = latest_ordinal(local_base_dir)
    if latest_local_ordinal is None:
        latest_remote_ordinal = latest_ordinal(remote_base_dir)
        if not latest_remote_ordinal:
            raise ToolchainAssertion(f"Can't find latest ordinal in {remote_base_dir}")
        print(cyan(f"You have no leveldb data under {local_base_dir}."))
        res = input(cyan(f"Would you like to copy #{latest_remote_ordinal} from {remote_base_dir}? [Y/n]"))
        if res.lower() in ["", "y", "yes"]:
            copy_leveldb_and_input_list(remote_base_dir, local_base_dir, latest_remote_ordinal)
        else:
            print(red(f"You must manually copy some data to {local_base_dir} to proceed."))
            raise ToolchainAssertion(f"You must manually copy some data to {local_base_dir} to proceed.")
    print(green(f"Using local {name} data under {local_base_dir}"))
    return local_base_dir
