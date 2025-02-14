# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import re

PYPI_PROJECT_URL_TEMPLATE = "https://pypi.org/simple/{}/"

PYTHON_HOSTED_URL = "https://files.pythonhosted.org/packages/"


# Distribution urls are formatted as:
# https://files.pythonhosted.org/packages/{hash path}/{filename}#sha256={content digest}
PYPI_DISTRIBUTION_URL_PATTERN = re.compile(rf"{PYTHON_HOSTED_URL}.*/(?P<filename>.*)#sha256=(?P<digest>.*)$")


def extract_digest(url):
    match = PYPI_DISTRIBUTION_URL_PATTERN.match(url)
    if match:
        return match.group("digest")
    raise ValueError(f"Expected a url matching `{PYPI_DISTRIBUTION_URL_PATTERN}`, but got {url}")


def extract_filename(url):
    match = PYPI_DISTRIBUTION_URL_PATTERN.match(url)
    if match:
        return match.group("filename")
    raise ValueError(f"Expected a url matching `{PYPI_DISTRIBUTION_URL_PATTERN}`, but got {url}")


def url_for_project(project_name):
    return PYPI_PROJECT_URL_TEMPLATE.format(project_name)
