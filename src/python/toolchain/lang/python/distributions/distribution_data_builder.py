# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import gzip
import json
import logging

from toolchain.lang.python.distributions.distribution_key import DistributionKey
from toolchain.util.file.base import File
from toolchain.util.leveldb.builder import Builder

logger = logging.getLogger(__name__)


class DistributionDataBuilder(Builder):
    """Utility code to build leveldbs from python distribution data."""

    def filter_input_file(self, input_file: File) -> bool:
        return input_file.path().endswith("json.gz")

    def process_input_file(self, input_file: File) -> None:
        input_data = json.loads(gzip.decompress(input_file.get_content()))
        for row in input_data:
            (
                filename,
                project_name,
                version,
                distribution_type,
                sha256_hexdigest,
                requires,
                requires_dist,
                requires_python,
                modules,
            ) = row
            key = DistributionKey.create(filename, project_name, version, distribution_type, requires_python)
            self.process_row(key, sha256_hexdigest, requires, requires_dist, modules)

    def process_row(
        self,
        key: DistributionKey,
        sha256_hexdigest: str,
        requires: list[str],
        requires_dist: list[str],
        modules: list[str],
    ):
        raise NotImplementedError
