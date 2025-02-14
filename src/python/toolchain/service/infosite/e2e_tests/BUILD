# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(sources=["*.py"])

pex_binary(
    name="infosite_e2e_tests",
    entry_point="test_infosite.py",
    dependencies=[
        ":e2e_tests",
    ],
)
