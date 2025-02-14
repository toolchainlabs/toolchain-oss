# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Allows reading command line arguments from environment variables.
# Based on https://stackoverflow.com/a/10551190/38265

import argparse
import os


class StoreWithEnvDefault(argparse.Action):
    def __init__(self, envvar=None, required=True, default=None, **kwargs):
        envvar = envvar or kwargs["dest"].upper()
        if not default and envvar and envvar in os.environ:
            default = os.environ[envvar]
        if required and default:
            required = False
        super().__init__(default=default, required=required, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
