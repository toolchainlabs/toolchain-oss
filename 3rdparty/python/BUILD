# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

pants_requirements(name="pants", resolve="pants-plugin")

# Edit requirements.txt in this directory to change deps.
python_requirements(
    module_mapping={
        "drf-nested-routers": ["rest_framework_nested"],
        "gitpython": ["git"],
        "hdrhistogram": ["hdrh"],
        "social-auth-core": ["social_core"],
        "social-auth-app-django": ["social_django"],
    }
)

python_requirements(
    name="pants-plugin-reqs",
    source="pants-plugin-reqs.txt",
    resolve="pants-plugin",
)

python_requirement(
    name="psycopg2",
    requirements=["psycopg2-binary==2.9.4; sys_platform!='darwin'", "psycopg2==2.9.4; sys_platform=='darwin'"],
    modules=["psycopg2"],
)
