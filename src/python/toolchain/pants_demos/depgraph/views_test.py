# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from urllib.parse import urlencode

import pytest
from bs4 import BeautifulSoup, Tag

from toolchain.pants_demos.depgraph.models import DemoRepo, GenerateDepgraphForRepo


@pytest.mark.django_db()
class TestAppView:
    def test_get(self, client) -> None:
        response = client.get("/")
        assert response.status_code == 200
        soup = BeautifulSoup(response.content, "html.parser")
        assert soup.select("title")[0].text == "Pants dependency inference in action"
        submit_button = soup.select("form button.button3")[0]
        assert submit_button.text == "go"


@pytest.mark.django_db()
class TestRepoSelectionView:
    def test_post_empty(self, client) -> None:
        response = client.post("/api/v1/repos/")
        assert response.status_code == 400
        assert response.content == b"repo-url not specified"

    @pytest.mark.parametrize(
        "url",
        [
            "https://github.com/pantsbuild/pants",
            "https://github.com/pantsbuild/pants/",
            "https://www.github.com/pantsbuild/pants/",
            "https://github.com/pantsbuild/pants/blob/main/.gitignore",
            "git@github.com:pantsbuild/pants.git",
            "https://github.com/pantsbuild/pants.git",
            "https://github.com/pantsbuild/pants.git/",
            "pantsbuild/pants",
            "pantsbuild/pants  ",
            "  pantsbuild/pants  ",
            "https://github.com/pantsbuild/pants.git/  ",
            "   https://github.com/pantsbuild/pants.git/  ",
        ],
    )
    def test_post_repo(self, client, httpx_mock, url: str) -> None:
        assert DemoRepo.objects.count() == 0
        assert GenerateDepgraphForRepo.objects.count() == 0
        httpx_mock.add_response(
            method="HEAD",
            url="https://github.com/pantsbuild/pants.git",
            status_code=200,
        )
        response = client.post(
            "/api/v1/repos/",
            data=urlencode({"repo-url": url}),
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code == 200
        assert response.json() == {
            "repo_full_name": "pantsbuild/pants",
            "account": "pantsbuild",
            "repo": "pants",
            "results_url": "/app/repo/pantsbuild/pants",
            "state": "not_processed",
        }
        assert DemoRepo.objects.count() == 1
        assert GenerateDepgraphForRepo.objects.count() == 1
        dr = DemoRepo.objects.first()
        assert dr.processing_state == DemoRepo.State.NOT_PROCESSED
        assert dr.repo_name == "pants"
        assert dr.repo_account == "pantsbuild"
        assert dr.id == GenerateDepgraphForRepo.objects.first().demo_repo_id
        request = httpx_mock.get_request()
        assert request.url == "https://github.com/pantsbuild/pants.git"

    def test_post_repo_not_accessible(self, client, httpx_mock) -> None:
        assert DemoRepo.objects.count() == 0
        assert GenerateDepgraphForRepo.objects.count() == 0
        httpx_mock.add_response(
            method="HEAD",
            url="https://github.com/pantsbuild/pants.git",
            status_code=404,
        )
        response = client.post(
            "/api/v1/repos/",
            data=urlencode({"repo-url": "https://github.com/pantsbuild/pants/blob/main/.gitignore"}),
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code == 400
        assert response.content == b"Can't access repo on GitHub.com"
        assert DemoRepo.objects.count() == 0
        assert GenerateDepgraphForRepo.objects.count() == 0
        request = httpx_mock.get_request()
        assert request.url == "https://github.com/pantsbuild/pants.git"

    @pytest.mark.parametrize(
        "url",
        [
            "https://nbc.com",
            "https://github.com/toolchain/",
            "https://github.com/bitnami/",
        ],
    )
    def test_post_repo_invalid_repos(self, client, url: str) -> None:
        assert DemoRepo.objects.count() == 0
        assert GenerateDepgraphForRepo.objects.count() == 0
        response = client.post(
            "/api/v1/repos/",
            data=urlencode({"repo-url": url}),
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code == 400
        assert response.content == b"Unsupported repo URL or not a github repo URL"

    @pytest.mark.parametrize(
        "url",
        [
            "https://github.org/pants/pantsbuild/",
            "https://bitbucket.org/asherf/minimal-pants/src/main/",
            "https://sourceforge.net/p/ruamel-yaml/code/ci/default/tree/",
            "https://api.github.com/pantsbuild/pants/",
        ],
    )
    def test_post_repo_not_github(self, client, url: str) -> None:
        assert DemoRepo.objects.count() == 0
        assert GenerateDepgraphForRepo.objects.count() == 0
        response = client.post(
            "/api/v1/repos/",
            data=urlencode({"repo-url": url}),
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code == 400
        assert response.content == b"Only GitHub is supported"

    def test_post_repo_completed(self, client, httpx_mock) -> None:
        dr = DemoRepo.create(account="django", repo="django")
        dr.set_failure_result(reason="no soup for you. come back one year!", processing_time=None)
        httpx_mock.add_response(
            method="HEAD",
            url="https://github.com/django/django.git",
            status_code=200,
        )
        response = client.post(
            "/api/v1/repos/",
            data=urlencode({"repo-url": "https://github.com/django/django/"}),
            content_type="application/x-www-form-urlencoded",
        )
        assert response.json() == {
            "repo_full_name": "django/django",
            "account": "django",
            "repo": "django",
            "error": "no soup for you. come back one year!",
            "results_url": "/app/repo/django/django",
            "state": "failure",
        }
        assert DemoRepo.objects.count() == 1
        assert GenerateDepgraphForRepo.objects.count() == 1
        dr = DemoRepo.objects.first()
        assert dr.processing_state == DemoRepo.State.FAILURE

    def test_post_repo_case_insensitive(self, client, httpx_mock) -> None:
        dr = DemoRepo.create(account="Django", repo="django")
        dr.set_failure_result(reason="no soup for you. come back one year!", processing_time=None)
        httpx_mock.add_response(
            method="HEAD",
            url="https://github.com/django/django.git",
            status_code=200,
        )
        response = client.post(
            "/api/v1/repos/",
            data=urlencode({"repo-url": "https://github.com/djAngO/djaNgo/"}),
            content_type="application/x-www-form-urlencoded",
        )
        assert response.json() == {
            "repo_full_name": "Django/django",
            "account": "Django",
            "repo": "django",
            "error": "no soup for you. come back one year!",
            "results_url": "/app/repo/Django/django",
            "state": "failure",
        }
        assert DemoRepo.objects.count() == 1
        assert GenerateDepgraphForRepo.objects.count() == 1
        dr = DemoRepo.objects.first()
        assert dr.processing_state == DemoRepo.State.FAILURE

    def test_post_repo_with_dot(self, client, httpx_mock) -> None:
        assert DemoRepo.objects.count() == 0
        assert GenerateDepgraphForRepo.objects.count() == 0
        httpx_mock.add_response(
            method="HEAD",
            url="https://github.com/lablup/backend.ai.git",
            status_code=200,
        )
        response = client.post(
            "/api/v1/repos/",
            data=urlencode({"repo-url": "https://github.com/lablup/backend.ai"}),
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code == 200
        assert response.json() == {
            "repo_full_name": "lablup/backend.ai",
            "account": "lablup",
            "repo": "backend.ai",
            "results_url": "/app/repo/lablup/backend.ai",
            "state": "not_processed",
        }
        assert DemoRepo.objects.count() == 1
        assert GenerateDepgraphForRepo.objects.count() == 1
        dr = DemoRepo.objects.first()
        assert dr.processing_state == DemoRepo.State.NOT_PROCESSED
        assert dr.repo_name == "backend.ai"
        assert dr.repo_account == "lablup"
        assert dr.id == GenerateDepgraphForRepo.objects.first().demo_repo_id
        request = httpx_mock.get_request()
        assert request.url == "https://github.com/lablup/backend.ai.git"

    def test_post_repo_with_long_slugs(self, client, httpx_mock) -> None:
        assert DemoRepo.objects.count() == 0
        assert GenerateDepgraphForRepo.objects.count() == 0
        account = "jerry" * 40
        repo = "seinfeld" * 100
        httpx_mock.add_response(
            method="HEAD",
            url=f"https://github.com/{account}/{repo}.git",
            status_code=200,
        )
        response = client.post(
            "/api/v1/repos/",
            data=urlencode({"repo-url": f"https://github.com/{account}/{repo}"}),
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code == 400
        assert response.content == b"This repo is not supported, repo and/or account name are too long."
        assert DemoRepo.objects.count() == 0
        assert GenerateDepgraphForRepo.objects.count() == 0


@pytest.mark.django_db()
class TestRepoApiView:
    def test_get_no_repo(self, client) -> None:
        response = client.get("/api/v1/repos/jerry/seinfeld/")
        assert response.status_code == 404

    def test_get_repo_not_processed(self, client) -> None:
        DemoRepo.create(account="bob", repo="sacamano")
        response = client.get("/api/v1/repos/bob/sacamano/")
        assert response.status_code == 200
        assert response.json() == {
            "repo_full_name": "bob/sacamano",
            "account": "bob",
            "repo": "sacamano",
            "results_url": "/app/repo/bob/sacamano",
            "state": "not_processed",
        }

    def test_get_repo_process_failure(self, client) -> None:
        dr = DemoRepo.create(account="bob", repo="sacamano")
        dr.set_failure_result(reason="no soup for you. come back one year!", processing_time=None)
        response = client.get("/api/v1/repos/bob/sacamano/")
        assert response.status_code == 200
        assert response.json() == {
            "repo_full_name": "bob/sacamano",
            "account": "bob",
            "repo": "sacamano",
            "results_url": "/app/repo/bob/sacamano",
            "state": "failure",
            "error": "no soup for you. come back one year!",
        }

    def test_case_insensitive(self, client) -> None:
        DemoRepo.create(account="StackStorm", repo="st2")
        response = client.get("/api/v1/repos/stackstorm/st2/")
        assert response.status_code == 200
        assert response.json() == {
            "repo_full_name": "StackStorm/st2",
            "account": "StackStorm",
            "repo": "st2",
            "results_url": "/app/repo/StackStorm/st2",
            "state": "not_processed",
        }


@pytest.mark.django_db()
class TestRepoView:
    def _get_robots_meta(self, response) -> Tag | None:
        soup = BeautifulSoup(response.content, "html.parser")
        return soup.find(name="meta", attrs={"name": "robots"})

    def test_get_repo_app_view(self, client) -> None:
        response = client.get("/app/repo/newman/hello")
        assert response.status_code == 200
        assert response.template_name == ["pants_demo/index.html"]
        assert set(response.context_data.keys()) == {
            "request",
            "account",
            "csrf_input",
            "sentry_dsn",
            "csrf_token",
            "js_bundles",
            "scripts_base",
            "repo",
            "view",
            "disable_indexing",
        }
        assert response.context_data["account"] == "newman"
        assert response.context_data["repo"] == "hello"
        assert response.context_data["disable_indexing"] is False
        assert response.context_data["js_bundles"] == [
            "/static/runtime.js",
            "/static/vendors~main.js",
            "/static/main.js",
        ]
        assert response.context_data["scripts_base"] == "/static/pants-demo-site/"
        assert response.context_data["sentry_dsn"] == "https://fake-sentry.jerry.crazy.joe-davola.net/opera"
        robots_no_index = self._get_robots_meta(response)
        assert robots_no_index is None

    def test_get_repo_app_view_disable_indexing(self, client) -> None:
        response = client.get("/app/repo/usps/newman")
        assert response.status_code == 200
        assert response.template_name == ["pants_demo/index.html"]
        assert set(response.context_data.keys()) == {
            "request",
            "account",
            "csrf_input",
            "sentry_dsn",
            "csrf_token",
            "js_bundles",
            "scripts_base",
            "repo",
            "view",
            "disable_indexing",
        }
        assert response.context_data["account"] == "usps"
        assert response.context_data["repo"] == "newman"
        assert response.context_data["disable_indexing"] is True
        assert response.context_data["js_bundles"] == [
            "/static/runtime.js",
            "/static/vendors~main.js",
            "/static/main.js",
        ]
        assert response.context_data["scripts_base"] == "/static/pants-demo-site/"
        assert response.context_data["sentry_dsn"] == "https://fake-sentry.jerry.crazy.joe-davola.net/opera"
        robots_no_index = self._get_robots_meta(response)
        assert robots_no_index is not None
        assert robots_no_index.attrs == {"name": "robots", "content": "noindex"}
