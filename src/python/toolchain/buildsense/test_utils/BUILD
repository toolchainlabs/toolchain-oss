# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    overrides={
        "fixtures_loader.py": {
            "resolve": parametrize("pants-plugin", "default-toolchain"),
            "dependencies": [":fixtures"],
        },
    }
)

resources(
    name="fixtures",
    sources=["fixtures/*.json", "fixtures/*.xml", "fixtures/*.txt"],
)
