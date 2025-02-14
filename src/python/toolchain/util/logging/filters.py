# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging


class SourcePathLoggingFilter(logging.Filter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        filter_file = __file__
        prefix_offset = filter_file.rindex(f"{__name__.replace('.', '/')}.py")
        tc_code_prefix = filter_file[:prefix_offset]
        # .whl and /site-packages prefixes are for installed packages (virtualenv)
        self._prefixes = [tc_code_prefix, ".whl/", "/site-packages/"]

    def filter(self, record):
        if record.pathname:
            record.pathname = self._clean_pathname(record.pathname)
        return super().filter(record)

    def _clean_pathname(self, pathname: str) -> str:
        for prefix in self._prefixes:
            if prefix in pathname:
                *_, pathname = pathname.partition(prefix)
                return pathname
        return pathname
