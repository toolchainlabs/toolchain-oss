# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.satresolver.pypi.python_distribution import PythonPackageDistribution


# TODO(Tansy): Add header including snapshot id, resolver version id, and maybe hash of input? (
#  requirements, python interpreter, architecture constraints, etc)
def generate_requirements(result) -> str:
    return "\n".join(
        [
            f"{distribution.package_name}=={distribution.version} --hash=sha256:{distribution.sha256_hexdigest}"
            for distribution in result
            if isinstance(distribution, PythonPackageDistribution)
        ]
    )
