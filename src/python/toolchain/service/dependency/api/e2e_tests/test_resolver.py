# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import pkg_resources
import pytest

from toolchain.service.dependency.api.e2e_tests.reslover_client import ResolveClient


def load_requirements(fixture_name: str) -> list[str]:
    content = pkg_resources.resource_string(__name__, f"fixtures/{fixture_name}.txt").decode()
    return [req.strip() for req in content.split("\n") if not req.startswith("#")]


class TestResolver:
    @pytest.fixture(scope="class")
    def client(self) -> ResolveClient:
        return ResolveClient(is_dev=True)

    @pytest.mark.parametrize("platform", ["manylinux2014_x86_64", "macosx_10_7_x86_64"])
    @pytest.mark.parametrize("python", ["3.6", "3.7", "3.8"])
    @pytest.mark.parametrize(
        "reqs_file",
        [
            "alerta-reqs",
            "caronc-apprise-reqs",
            "django-reqs",
            "django-shop-reqs",
            "django-drf-filepond-reqs",
            "facebook-prophet",
            "face_recognition-reqs",
            "ouroboros-reqs",
            "pants-reqs",
            "pgcli-reqs",
            "plotly-dash-reqs",
            "pypa-warehouse-reqs",
            "pyspider-reqs",
            "modoboa-reqs",
            "mypy-reqs",
        ],
    )
    def test_resolve_reqs_all_python_3(self, reqs_file, platform, python, client):
        requirements = load_requirements(reqs_file)
        resolver_run, response = client.resolve(requirement_strings=requirements, python=python, platform=platform)

    @pytest.mark.parametrize("platform", ["manylinux2014_x86_64", "macosx_10_7_x86_64"])
    @pytest.mark.parametrize("python", ["3.6", "3.7"])
    @pytest.mark.parametrize("reqs_file", ["deezer-spleeter-reqs"])
    def test_resolve_reqs_all_python_36_and_37(self, reqs_file, platform, python, client):
        requirements = load_requirements(reqs_file)
        resolver_run, response = client.resolve(requirement_strings=requirements, python=python, platform=platform)
