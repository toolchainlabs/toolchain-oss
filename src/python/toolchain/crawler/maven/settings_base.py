# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.django.site.settings.service import *  # noqa: F403

INSTALLED_APPS.extend(
    [
        "toolchain.crawler.base.apps.CrawlerBaseAppConfig",
        "toolchain.crawler.maven.apps.CrawlerMavenAppConfig",
        "toolchain.packagerepo.maven.apps.PackageRepoMavenAppConfig",
        "toolchain.django.webresource.apps.WebResourceAppConfig",
    ]
)

set_up_databases(__name__, "maven")

# The prod bucket contains canonical data corresponding to the prod maven database.
# The dev bucket is shared for all dev maven databases, and so keys in it are prefixed by namespace.
_maven_bucket_prefix = "maven" if TOOLCHAIN_ENV.is_prod else "maven-dev"  # type: ignore[attr-defined]
WEBRESOURCE_BUCKET = config.get("WEBRESOURCE_BUCKET", f"{_maven_bucket_prefix}.{AWS_REGION}.toolchain.com")
WEBRESOURCE_KEY_PREFIX = NAMESPACE

_kythe_bucket_prefix = "kythe" if TOOLCHAIN_ENV.is_prod else "kythe-dev"  # type: ignore[attr-defined]
KYTHE_ENTRIES_BUCKET = config.get("KYTHE_ENTRIES_BUCKET", f"{_kythe_bucket_prefix}.{AWS_REGION}.toolchain.com")
KYTHE_ENTRIES_KEY_PREFIX = NAMESPACE

# Set to True to store the content of small text files in the web resource database record, instead of on S3.
INLINE_SMALL_WEBRESOURCE_TEXT_CONTENT = config.is_set("INLINE_SMALL_WEBRESOURCE_TEXT_CONTENT")
# Store text shorter than this directly in the database. Larger text content, or binary content, is stored on S3.
MAX_INLINE_TEXT_SIZE = config.get("MAX_INLINE_WEBRESOURCE_TEXT_SIZE", 4 * 1024)

# Set to True to download .sha1 files and verify file contents against them.
# If false we skip the verification and proceed as-if the file is verified.
VERIFY_SHA1S = config.is_set("VERIFY_SHA1S")

# Set to True to process POM files, including resolving parents, extracting dependencies, etc.
PROCESS_POM_FILES = config.is_set("PROCESS_POM_FILES")

# Set to True to download .jar files.
DOWNLOAD_JARS = config.is_set("DOWNLOAD_JARS")

# Set to True to follow dependencies mentioned in POM files.
# If False we extract and store the dependency information from the POM but don't act on it.
FOLLOW_POM_DEPENDENCIES = config.is_set("FOLLOW_POM_DEPENDENCIES")
