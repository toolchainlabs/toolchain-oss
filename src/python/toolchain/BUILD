# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        "3rdparty/python#django-prometheus",  # via _COMMON_MIDDLEWARE and _COMMON_APPS
        "3rdparty/python#pytest-django",
        "3rdparty/python#pytest-httpx",
        "3rdparty/python#pytest-responses",
    ],
)

python_tests(name="tests")


python_distribution(
    name="toolchain-pants-plugin",
    wheel=True,
    sdist=True,
    dependencies=[
        "!!3rdparty/python:pants#pantsbuild.pants",
        "src/python/toolchain/pants",
        "src/python/toolchain/pants/auth",
        "src/python/toolchain/pants/buildsense",
        "src/python/toolchain/pants/common",
    ],
    provides=setup_py(
        name="toolchain.pants.plugin",
        description="Toolchain Pants plugin.",
        long_desc_file="src/python/toolchain/pants/plugin_desc.md",
        project_urls={
            "Changelog": "https://docs.toolchain.com/docs/toolchain-pants-plugin-changelog",
            "Documentation": "https://docs.toolchain.com/docs/getting-started-with-toolchain",
            "Twitter": "https://twitter.com/toolchainlabs",
        },
        additional_classifiers=[
            "Development Status :: 4 - Beta",
            "Environment :: Plugins",
            "Programming Language :: Python :: 3 :: Only",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: 3.8",
            "Programming Language :: Python :: 3.9",
        ],
        python_requires=">=3.7.2,<3.10",  # Should match pants.toml [python.resolves_to_interpreter_constraints].pants-plugin
        entry_points={
            "pantsbuild.plugin": [
                "rules=toolchain.pants.register:rules",
                "remote_auth=toolchain.pants.auth.plugin:toolchain_auth_plugin",
            ]
        },
    ),
)

python_test_utils(name="test_utils")
