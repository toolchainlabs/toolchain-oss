# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Migrations run under toolshed service. so they are included here
python_sources(
    dependencies=[
        "src/python/toolchain/buildsense/ingestion",
        "src/python/toolchain/buildsense/ingestion/migrations",
        "src/python/toolchain/buildsense/migrations",
        "src/python/toolchain/crawler/base",
        "src/python/toolchain/crawler/base/migrations",
        "src/python/toolchain/crawler/pypi",
        "src/python/toolchain/crawler/pypi/migrations",
        "src/python/toolchain/dependency/migrations",
        "src/python/toolchain/django/service/gunicorn",
        "src/python/toolchain/django/site/migrations",
        "src/python/toolchain/django/webresource",
        "src/python/toolchain/django/webresource/migrations",
        "src/python/toolchain/bitbucket_integration/migrations",
        "src/python/toolchain/bitbucket_integration",
        "src/python/toolchain/oss_metrics/migrations",
        "src/python/toolchain/oss_metrics/bugout_integration/migrations",
        "src/python/toolchain/github_integration/migrations",
        "src/python/toolchain/packagerepo/pypi",
        "src/python/toolchain/packagerepo/pypi/migrations",
        "src/python/toolchain/pants_demos/depgraph/migrations",
        "src/python/toolchain/toolshed",
        "src/python/toolchain/toolshed/management/commands",
        "src/python/toolchain/users",
        "src/python/toolchain/users/migrations",
        "src/python/toolchain/workflow",
        "src/python/toolchain/workflow/migrations",
        "src/python/toolchain/payments/stripe_integration/migrations",
        "src/python/toolchain/payments/amberflo_integration/migrations",
        "src/python/toolchain/notifications/email/migrations",
    ],
)

pex_binary(
    name="toolshed-manage",
    entry_point="manage.py",
    dependencies=[
        ":toolshed",
    ],
)

pex_binary(
    name="toolshed-gunicorn",
    entry_point="gunicorn_main.py",
    dependencies=[
        ":toolshed",
    ],
)
