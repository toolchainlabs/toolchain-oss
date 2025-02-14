# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from pants.backend.python.goals.setup_py import SetupKwargs, SetupKwargsRequest
from pants.engine.fs import DigestContents, GlobMatchErrorBehavior, PathGlobs
from pants.engine.rules import Get, rule
from pants.engine.target import Target
from pants.engine.unions import UnionRule

from toolchain.pants.version import VERSION

_COMMON_CLASSIFIERS = (
    "Intended Audience :: Developers",
    "License :: Other/Proprietary License",
    "Operating System :: MacOS :: MacOS X",
    "Operating System :: POSIX :: Linux",
    "Programming Language :: Python",
    "Topic :: Software Development :: Build Tools",
)


class ToolchainSetupKwargsRequest(SetupKwargsRequest):
    @classmethod
    def is_applicable(cls, _: Target) -> bool:
        return True


@rule
async def toolchain_setup_plugin(request: ToolchainSetupKwargsRequest) -> SetupKwargs:
    explicit_kwargs = request.explicit_kwargs
    digest_contents = await Get(
        DigestContents,
        PathGlobs(
            [explicit_kwargs.pop("long_desc_file")],
            description_of_origin="`setup_py()` plugin",
            glob_match_error_behavior=GlobMatchErrorBehavior.error,
        ),
    )
    classifiers = list(_COMMON_CLASSIFIERS) + request.explicit_kwargs.pop("additional_classifiers")
    explicit_kwargs.update(
        version=VERSION,
        long_description=digest_contents[0].content.decode(),
        long_description_content_type="text/markdown",
        url="https://toolchain.com",
        license="Proprietary",
        classifiers=classifiers,
        author="Toolchain Inc",
        author_email="info@toolchain.com",
    )

    return SetupKwargs(explicit_kwargs, address=request.target.address)


def toolchain_setup_rules():
    return [toolchain_setup_plugin, UnionRule(SetupKwargsRequest, ToolchainSetupKwargsRequest)]
