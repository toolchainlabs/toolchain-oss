# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import re


def camel_to_dashes(s):
    return re.sub("([A-Z])", "-\\1", s).lower().lstrip("-").replace("_", "-")
