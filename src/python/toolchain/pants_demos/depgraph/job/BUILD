# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources()

resources(name="resources", sources=["resources/*"])

pex_binary(name="pants-demo", entry_point="demo.py", dependencies=[":resources"])
