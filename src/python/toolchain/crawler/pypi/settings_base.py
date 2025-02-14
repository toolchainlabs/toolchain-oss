# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.crawler.pypi.constants import APPS
from toolchain.django.site.settings.service import *  # noqa: F403

INSTALLED_APPS.extend(APPS)

set_up_databases(__name__, "pypi")

# The prod bucket contains canonical data corresponding to the prod pypi database.
# The dev bucket is shared for all dev pypi databases, and so keys in it are prefixed by namespace.
_bucket_prefix = "pypi" if TOOLCHAIN_ENV.is_prod else "pypi-dev"  # type: ignore[attr-defined]
if TOOLCHAIN_ENV.is_dev:  # type: ignore[attr-defined]
    WEBRESOURCE_BUCKET = config.get("WEBRESOURCE_BUCKET", "pypi-dev.us-east-1.toolchain.com")
    WEBRESOURCE_KEY_PREFIX = config.get("WEBRESOURCE_KEY_PREFIX", NAMESPACE)
elif TOOLCHAIN_ENV.is_prod:  # type: ignore[attr-defined]
    WEBRESOURCE_BUCKET = config["WEBRESOURCE_BUCKET"]
    WEBRESOURCE_KEY_PREFIX = config["WEBRESOURCE_KEY_PREFIX"]


# Set to True to store the content of small text files in the web resource database record, instead of on S3.
INLINE_SMALL_WEBRESOURCE_TEXT_CONTENT = config.is_set("INLINE_SMALL_WEBRESOURCE_TEXT_CONTENT")
# Store text shorter than this directly in the database. Larger text content, or binary content, is stored on S3.
MAX_INLINE_TEXT_SIZE = config.get("MAX_INLINE_WEBRESOURCE_TEXT_SIZE", 4 * 1024)
