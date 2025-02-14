# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.pants.auth.plugin import toolchain_auth_plugin
from toolchain.pants.auth.rules import get_auth_rules
from toolchain.pants.buildsense.rules import rules_buildsense_reporter

# Allows pants to automatically detect the remote auth plugin and activate it.
remote_auth = toolchain_auth_plugin


def rules():
    return (
        *get_auth_rules(),
        *rules_buildsense_reporter(),
    )
