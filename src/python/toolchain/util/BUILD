# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources()

python_sources(
    name="pants-plugin",
    sources=["constants.py"],
    resolve="pants-plugin",
    interpreter_constraints=[">=3.7.2,<3.10"],
    skip_pyupgrade=True,  # since the rest of the repo is python 3.9 and pyupgrade enforces new syntax
)
