# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
from pathlib import Path

import pytest
from rest_framework.test import APIClient

from toolchain.django.auth.claims import RepoClaims
from toolchain.django.auth.constants import AccessTokenAudience, AccessTokenType
from toolchain.django.auth.utils import create_internal_auth_headers
from toolchain.django.site.models import ToolchainUser
from toolchain.django.webresource.models import WebResource
from toolchain.lang.python.distributions.distribution_type import DistributionType
from toolchain.lang.python.modules.module_distribution_map_test import MODULES_MAP_2, create_fake_modules_map
from toolchain.packagerepo.pypi.models import DistributionData, Project
from toolchain.util.leveldb.test_helpers.utils import FakeReloadableDataset
from toolchain.util.test.prometheus_utils import assert_latest_metric_equals
from toolchain.util.test.util import convert_headers_to_wsgi


def _get_client(user: ToolchainUser, claims: RepoClaims) -> APIClient:
    headers = create_internal_auth_headers(user, claims=claims.as_json_dict(), impersonation=None)
    return APIClient(**convert_headers_to_wsgi(headers))


@pytest.mark.django_db()
class TestViewsAuth:
    def test_invalid_audience(self) -> None:
        user = ToolchainUser.create(username="kramer", email="kramer@jerrysplace.com")
        claims = RepoClaims(
            user_api_id=user.api_id,
            customer_pk="tuesday-has-no-feel",
            repo_pk="sniffing",
            username="darren",
            audience=AccessTokenAudience.BUILDSENSE_API,
            token_type=AccessTokenType.REFRESH_TOKEN,
            token_id="soup",
            restricted=False,
        )
        client = _get_client(user, claims)
        response = client.get("/v1/packagerepo/pypi/")
        assert response.status_code == 403
        assert response.json() == {"detail": "You do not have permission to perform this action."}

    def test_inactive_user(self) -> None:
        user = ToolchainUser.create(username="kramer", email="kramer@jerrysplace.com")
        claims = RepoClaims(
            user_api_id="oppsite",
            customer_pk="jor-el",
            repo_pk="bosco",
            username="kramer",
            audience=AccessTokenAudience.DEPENDENCY_API,
            token_type=AccessTokenType.REFRESH_TOKEN,
            token_id="soup",
            restricted=False,
        )

        client = _get_client(user, claims)
        user.deactivate()
        response = client.get("/v1/packagerepo/pypi/")
        assert response.status_code == 403
        assert response.json() == {"detail": "Authentication credentials were not provided."}

    def test_no_auth(self) -> None:
        response = APIClient().get("/v1/packagerepo/pypi/")
        assert response.status_code == 403
        assert response.json() == {"detail": "Authentication credentials were not provided."}


@pytest.mark.django_db()
class BaseViewsTest:
    @pytest.fixture(
        params=[
            AccessTokenAudience.for_pants_client() | AccessTokenAudience.DEPENDENCY_API,
            AccessTokenAudience.DEPENDENCY_API,
        ]
    )
    def client(self, request):
        user = ToolchainUser.create(username="kramer", email="kramer@jerrysplace.com")
        claims = RepoClaims(
            user_api_id=user.api_id,
            customer_pk="salmon",
            repo_pk="tuna",
            username="darren",
            audience=request.param,
            token_type=AccessTokenType.REFRESH_TOKEN,
            token_id="soup",
            restricted=False,
        )
        return _get_client(user, claims)


class TestViews(BaseViewsTest):
    @pytest.fixture()
    def pypi_project(self) -> Project:
        return Project.get_or_create("foo")

    def test_get_packagerepos(self, client) -> None:
        response = client.get("/v1/packagerepo/")
        assert response.status_code == 200
        assert response.json() == ["maven", "pypi"]

    def test_get_packagerepo(self, client) -> None:
        response = client.get("/v1/packagerepo/pypi/")
        assert response.status_code == 200
        assert response.json() == {"name": "pypi"}

    def test_get_invalid_packagerepo(self, client) -> None:
        response = client.get("/v1/packagerepo/foo/")
        assert response.status_code == 404

    def test_get_pypi_project(self, client, pypi_project: Project) -> None:
        response = client.get("/v1/packagerepo/pypi/projects/foo/")
        assert response.status_code == 200
        assert response.json() == {"name": pypi_project.name, "pypi_url": pypi_project.pypi_url, "releases": []}

    def test_get_pypi_project_releases(self, client, pypi_project: Project) -> None:
        pypi_project.releases.create(version="0.0.1")

        response = client.get("/v1/packagerepo/pypi/projects/foo/releases/")
        assert response.status_code == 200
        assert response.json() == {"results": [{"version": "0.0.1"}], "next": None, "previous": None}

    def test_get_pypi_project_release(self, client, pypi_project: Project) -> None:
        pypi_project.releases.create(version="0.0.4")

        response = client.get("/v1/packagerepo/pypi/projects/foo/releases/0.0.4/")
        assert response.status_code == 200
        assert response.json() == {"version": "0.0.4"}

    def test_get_pypi_project_release_artifacts(self, client, pypi_project: Project) -> None:
        release = pypi_project.releases.create(version="0.0.5")
        dist = release.distributions.create(
            filename="foo-0-0-5.whl", serial_from=2, dist_type=DistributionType.WHEEL.value
        )
        web_resource = WebResource.objects.create()
        DistributionData.objects.create(
            distribution=dist, web_resource=web_resource, metadata={}, modules=["mod1", "mod2"]
        )

        response = client.get("/v1/packagerepo/pypi/projects/foo/releases/0.0.5/artifacts/")

        assert response.status_code == 200
        assert response.json() == {
            "results": [
                {
                    "filename": "foo-0-0-5.whl",
                    "dist_type": "WHEEL",
                    "release": {"version": "0.0.5"},
                    "data": {"modules": ["mod1", "mod2"]},
                }
            ],
            "next": None,
            "previous": None,
        }

    def test_get_pypi_project_release_artifact(self, client, pypi_project: Project) -> None:
        release = pypi_project.releases.create(version="0.0.6")
        dist = release.distributions.create(
            filename="foo-0-0-6.whl", serial_from=2, dist_type=DistributionType.WHEEL.value
        )
        web_resource = WebResource.objects.create()
        DistributionData.objects.create(
            distribution=dist, web_resource=web_resource, metadata={}, modules=["mod3", "mod4"]
        )

        response = client.get("/v1/packagerepo/pypi/projects/foo/releases/0.0.6/artifacts/foo-0-0-6.whl/")

        assert response.status_code == 200
        assert response.json() == {
            "filename": "foo-0-0-6.whl",
            "dist_type": "WHEEL",
            "release": {"version": "0.0.6"},
            "data": {"modules": ["mod3", "mod4"]},
        }

    def test_get_pypi_projects(self, client, pypi_project: Project) -> None:
        response = client.get("/v1/packagerepo/pypi/projects/")
        assert response.status_code == 200
        assert response.json() == {
            "results": [{"name": pypi_project.name, "pypi_url": pypi_project.pypi_url, "releases": []}],
            "next": None,
            "previous": None,
        }

    def test_get_maven_project(self, client) -> None:
        response = client.get("/v1/packagerepo/maven/projects/bar/")
        assert response.status_code == 400
        assert response.json() == {"detail": "API not supported for 'maven'"}


class TestDistributionsViewSet(BaseViewsTest):
    @pytest.fixture()
    def fake_modules_dist_dataset(self, tmp_path: Path):
        db_path = tmp_path / "leveldbs" / "02961"
        db_path.mkdir(parents=True)
        return FakeReloadableDataset(create_fake_modules_map(db_path, MODULES_MAP_2))

    def test_list_distributions_for_module(self, client, settings, fake_modules_dist_dataset) -> None:
        settings.MODULE_DISTRIBUTION_MAP = fake_modules_dist_dataset
        response = client.get("/v1/packagerepo/pypi/distributions/", data={"module_list": "bookman,junior"})
        assert response.status_code == 200
        assert response.json() == {
            "data_version": 2961,
            "results": {
                "bookman": [
                    {"name": "joke", "version": "1.8.0"},
                    {"name": "library", "version": "0.2.882"},
                    {"name": "library", "version": "3.24.0"},
                ],
                "junior": [{"name": "nypl", "version": "6.2.0.dev33"}, {"name": "nypl", "version": "81.0.22"}],
            },
        }

    def test_empty_query(self, client, settings, fake_modules_dist_dataset) -> None:
        settings.MODULE_DISTRIBUTION_MAP = fake_modules_dist_dataset
        response = client.get("/v1/packagerepo/pypi/distributions/")
        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid module list:. "}

    def test_large_query(self, client, settings, fake_modules_dist_dataset) -> None:
        settings.MODULE_DISTRIBUTION_MAP = fake_modules_dist_dataset
        modules_list = ",".join(f"shrimp-{i}" for i in range(101))
        response = client.get("/v1/packagerepo/pypi/distributions/", data={"module_list": modules_list})
        assert response.status_code == 400
        assert response.json() == {"detail": "Exceeded maximum number of modules request (max: 100, got: 101)"}

    @pytest.mark.parametrize("bad_modules_list", ["", ", , ,", "jerry, handicap", "  hulk"])
    def test_invalid_query(self, client, settings, fake_modules_dist_dataset, bad_modules_list):
        settings.MODULE_DISTRIBUTION_MAP = fake_modules_dist_dataset
        response = client.get("/v1/packagerepo/pypi/distributions/", data={"module_list": bad_modules_list})
        assert response.status_code == 400
        assert response.json() == {"detail": f"Invalid module list:. {bad_modules_list}"}


class TestModulesViewSet(BaseViewsTest):
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        foo_proj = Project.get_or_create("foo")
        bar_proj = Project.get_or_create("bar")
        foo5 = foo_proj.releases.create(version="0.0.5")
        foo6 = foo_proj.releases.create(version="0.0.6")
        bar13 = bar_proj.releases.create(version="0.0.13")

        foo5_whl = foo5.distributions.create(
            filename="foo-0-0-5.whl", serial_from=2, url="foo-0-0-5.whl", dist_type=DistributionType.WHEEL.value
        )
        foo6_whl = foo6.distributions.create(
            filename="foo-0-0-6.whl", serial_from=4, url="foo-0-0-6.whl", dist_type=DistributionType.WHEEL.value
        )
        foo6_sdist = foo6.distributions.create(
            filename="foo-0-0-6.tar.gz", serial_from=4, url="foo-0-0-6.tar.gz", dist_type=DistributionType.SDIST.value
        )
        bar13_whl = bar13.distributions.create(
            filename="bar-0-0-13.whl", serial_from=56, url="bar-0-0-13.whl", dist_type=DistributionType.WHEEL.value
        )

        DistributionData.objects.create(
            distribution=foo5_whl,
            web_resource=WebResource.objects.create(url="foo5.whl"),
            metadata={},
            modules=["foo1", "foo2"],
        )
        DistributionData.objects.create(
            distribution=foo6_whl,
            web_resource=WebResource.objects.create(url="foo6.whl"),
            metadata={},
            modules=["foo1", "foo2", "foo3"],
        )
        DistributionData.objects.create(
            distribution=foo6_sdist,
            web_resource=WebResource.objects.create(url="foo6.tar.gz"),
            metadata={},
            modules=["foo1", "foo2", "foo3"],
        )
        DistributionData.objects.create(
            distribution=bar13_whl,
            web_resource=WebResource.objects.create(url="bar13.whl"),
            metadata={},
            modules=["bar1", "bar2"],
        )

    def test_single_query_clause(self, client) -> None:
        query = json.dumps({"project_name": "foo", "version": "0.0.5"})
        response = client.get("/v1/packagerepo/pypi/modules/", [("q", query)])

        assert_latest_metric_equals("toolchain_api_module_distributions", 1)
        assert response.status_code == 200
        assert response.json() == {
            "results": [
                {"project_name": "foo", "version": "0.0.5", "filename": "foo-0-0-5.whl", "modules": ["foo1", "foo2"]}
            ]
        }

    def test_multiple_query_clause(self, client) -> None:
        query = json.dumps([{"project_name": "foo", "version": "0.0.6"}, {"project_name": "bar", "version": "0.0.13"}])
        response = client.get("/v1/packagerepo/pypi/modules/", [("q", query)])

        assert_latest_metric_equals("toolchain_api_module_distributions", 2)
        assert response.status_code == 200
        assert response.json() == {
            "results": [
                {"project_name": "bar", "version": "0.0.13", "filename": "bar-0-0-13.whl", "modules": ["bar1", "bar2"]},
                {
                    "project_name": "foo",
                    "version": "0.0.6",
                    "filename": "foo-0-0-6.tar.gz",
                    "modules": ["foo1", "foo2", "foo3"],
                },
                {
                    "project_name": "foo",
                    "version": "0.0.6",
                    "filename": "foo-0-0-6.whl",
                    "modules": ["foo1", "foo2", "foo3"],
                },
            ]
        }

    def test_complex_query_clause(self, client) -> None:
        query = json.dumps([{"filename": "bar-0-0-13.whl"}, {"project_name": "foo"}])  # By filename.  # No version.
        response = client.get("/v1/packagerepo/pypi/modules/", [("q", query)])

        assert_latest_metric_equals("toolchain_api_module_distributions", 2)
        assert response.status_code == 200
        assert response.json() == {
            "results": [
                {"project_name": "bar", "version": "0.0.13", "filename": "bar-0-0-13.whl", "modules": ["bar1", "bar2"]},
                {"project_name": "foo", "version": "0.0.5", "filename": "foo-0-0-5.whl", "modules": ["foo1", "foo2"]},
                {
                    "project_name": "foo",
                    "version": "0.0.6",
                    "filename": "foo-0-0-6.tar.gz",
                    "modules": ["foo1", "foo2", "foo3"],
                },
                {
                    "project_name": "foo",
                    "version": "0.0.6",
                    "filename": "foo-0-0-6.whl",
                    "modules": ["foo1", "foo2", "foo3"],
                },
            ]
        }

    def test_query_by_package_names_and_versions(self, client) -> None:
        query = "foo==0.0.6,bar==0.0.13"
        response = client.get("/v1/packagerepo/pypi/modules/", [("q", query)])

        assert_latest_metric_equals("toolchain_api_module_distributions", 2)
        assert response.status_code == 200
        assert response.json() == {
            "results": [
                {"project_name": "bar", "version": "0.0.13", "filename": "bar-0-0-13.whl", "modules": ["bar1", "bar2"]},
                {
                    "project_name": "foo",
                    "version": "0.0.6",
                    "filename": "foo-0-0-6.tar.gz",
                    "modules": ["foo1", "foo2", "foo3"],
                },
                {
                    "project_name": "foo",
                    "version": "0.0.6",
                    "filename": "foo-0-0-6.whl",
                    "modules": ["foo1", "foo2", "foo3"],
                },
            ]
        }

    def test_max_queries(self, client) -> None:
        qs = ",".join(f"izzy-{i}==1.{i}.0" for i in range(401))
        response = client.get("/v1/packagerepo/pypi/modules/", [("q", qs)])
        assert response.status_code == 400
        assert response.json() == {
            "errors": {
                "q": [{"code": "", "message": "Exceeded maximum number of queries per request (max: 400, got: 401)"}]
            }
        }

    @pytest.mark.parametrize(
        "bad_query",
        [
            "jerry=0.0.6,vandelay==0.0.13",
            "==1.2.3,massage==1.22.33",
            "{no soup for you",
            "[stringy,plump,juicy]",
            '{"show": "business"}',
            '{"filename": "elaine", "version": "222.00.333"}',
            '{"version": "222.00.333"}',
            "[]",
            "  ",
        ],
    )
    def test_invalid_query(self, client, bad_query) -> None:
        response = client.get("/v1/packagerepo/pypi/modules/", [("q", bad_query)])
        assert response.status_code == 400
        # assert response.json() == {'errors': {'q': [{'code': '', 'message': f'Invalid query: {bad_query}'}]}}
