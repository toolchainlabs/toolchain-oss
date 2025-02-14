# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
import os
import tarfile
import zipfile

import pkginfo

from toolchain.base.toolchain_error import ToolchainError
from toolchain.lang.python.distributions.distribution_type import DistributionType
from toolchain.lang.python.distributions.sdist_reader import SDistReader

_logger = logging.getLogger(__name__)


def extract_metadata(path: str) -> tuple[DistributionType, dict]:
    """Extracts the metadata from a python distribution."""
    # Note: pkginfo will parse the requirements correctly for the current system architecture.
    try:
        dist = pkginfo.get_metadata(path)
        if dist is None:
            # Can happen if there's no PKG-INFO.
            return DistributionType.SDIST, {}
        description = getattr(dist, "description", None) or ""
        # This is a real-world problem that causes failures down the line, so we fix now.
        # See, e.g., https://pypi.org/project/add1-pkg/.
        has_nul = "\0" in description
        metadata = vars(dist)
        if isinstance(dist, pkginfo.SDist):
            # Few sdists declare their reqs in metadata. But many specify them in a requires.txt file.
            # So we override what pkginfo read with our more sophisticated sdist metadata collector.
            # If it's empty, meaning we failed to read any metadata the sophisticated way, fall back to the original.
            metadata = SDistReader.open_sdist(path).get_metadata() or metadata
        if has_nul:
            metadata["description"] = "description containing nul bytes was omitted."
        return DistributionType.from_pkginfo_distribution(dist), metadata
    except (EOFError, tarfile.ReadError, zipfile.BadZipFile) as e:
        raise ToolchainError(f"Failed to extract metadata from {os.path.basename(path)}: {e}")
