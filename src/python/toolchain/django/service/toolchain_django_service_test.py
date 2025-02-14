# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import sys
from contextlib import contextmanager
from importlib.abc import Loader
from importlib.machinery import ModuleSpec
from importlib.util import module_from_spec

import pytest

from toolchain.django.service.gunicorn.toolchain_gunicorn_service import ToolchainGunicornService
from toolchain.django.service.workflow.toolchain_workflow_service import ToolchainWorkflowService


def synthesize_empty_module(module_name):
    return module_from_spec(ModuleSpec(module_name, Loader(), is_package=False))


@contextmanager
def create_standard_django_service_modules(service_package):
    original_sys_modules = sys.modules.copy()

    # We expect django services to have manage.py and settings.py in their root package, this
    # simulates those minimally.
    for sentinel in ("manage", "settings"):
        module_name = f"{service_package}.{sentinel}"
        sys.modules[module_name] = synthesize_empty_module(module_name)

    try:
        yield
    finally:
        sys.modules = original_sys_modules


@pytest.mark.parametrize(
    ("service_name", "service_package", "service_cls"),
    [
        ("infosite", "toolchain.service.infosite", ToolchainGunicornService),
        ("buildsense/api", "toolchain.service.buildsense.api", ToolchainGunicornService),
        ("crawler/pypi/workflow", "toolchain.service.crawler.pypi.workflow", ToolchainWorkflowService),
    ],
)
def test_settings_module_for_service(service_name, service_package, service_cls):
    with create_standard_django_service_modules(service_package):
        assert f"{service_package}.settings" == service_cls(service_name)._settings_module


_PFX = "src/python/toolchain/service/"


@pytest.mark.parametrize(
    ("filename", "service_package", "service_name", "parts", "service_cls"),
    [
        (_PFX + "users/ui/manage.py", "toolchain.service.users.ui", "users/ui", 2, ToolchainGunicornService),
        (_PFX + "infosite/manage.py", "toolchain.service.infosite", "infosite", 1, ToolchainGunicornService),
        (
            _PFX + "buildsense/api/gunicorn_main.py",
            "toolchain.service.buildsense.api",
            "buildsense/api",
            2,
            ToolchainGunicornService,
        ),
        (
            _PFX + "dependency/api/manage.py",
            "toolchain.service.dependency.api",
            "dependency/api",
            2,
            ToolchainGunicornService,
        ),
        (
            _PFX + "crawler/pypi/workflow/manage.py",
            "toolchain.service.crawler.pypi.workflow",
            "crawler/pypi/workflow",
            3,
            ToolchainWorkflowService,
        ),
        (
            _PFX + "servicerouter/gunicorn_main.py",
            "toolchain.service.servicerouter",
            "servicerouter",
            1,
            ToolchainGunicornService,
        ),
        # this happens when running collect_static when building the pex file (in docker)
        (
            "/home/toolchain/.pex/code/xxxxxssssss44/toolchain/service/buildsense/api/manage.py",
            "toolchain.service.buildsense.api",
            "buildsense/api",
            2,
            ToolchainGunicornService,
        ),
    ],
)
def test_from_name(filename, service_package, service_name, parts, service_cls):
    with create_standard_django_service_modules(service_package):
        svc = service_cls.from_file_name(filename)
        assert svc._service.service_name == service_name
        assert svc._settings_module == f"{service_package}.settings"
        # Double check to make sure the separator is a forward slash. we have code that relies on it (UsersDBRouter)
        assert len(svc._service.service_name.split("/")) == parts


@pytest.mark.parametrize(
    "bad_name",
    [
        "src/python/toolchain/service/",
        "src/python/toolchain/service",
        "src/python/toolchain/",
        "src/python/toolchain/service/crawler/pypi/",
        "src/python/toolchain/service/crawler/pypi/gunicorn.py",
        "src/python/toolchain/service/crawler/pypi/manage.pyx",
        "src/python/toolchain/service/crawler/pypi",
        "src/python/toolchain/service/infosite/",
        "src/python/toolchain/service/infosite",
        "src/python/toolchain/service/infosite/gunicorn.py",
        "src/python/toolchain/service/infosite/main.py",
        "/home/toolchain/.pex/code/xxxxxssssss44/toolchain/service/buildsense/api/clear.py",
        "/home/toolchain/.pex/code/xxxxxssssss44/toolchain/buildsense/api/manage.py",
    ],
)
def test_invalid_name(bad_name):
    with pytest.raises(ToolchainGunicornService.InvalidServiceFile):
        ToolchainGunicornService.from_file_name(bad_name)
