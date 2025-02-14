# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

import pytest
from faker import Faker

from toolchain.pants_demos.depgraph.models import DemoRepo


@pytest.mark.django_db()
class TestDemoReposSitemap:
    def test_empty(self, client) -> None:
        response = client.get("/sitemap.xml")
        assert response.status_code == 200
        assert response.context_data["urlset"] == []
        assert (
            response.content
            == b'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n\n</urlset>\n'
        )

    def _add_repo(self, account: str, repo: str, fk: Faker) -> DemoRepo:
        dr = DemoRepo.create(account=account, repo=repo)
        dr.set_success_result(
            branch=fk.word(),
            commit_sha=fk.sha1(),
            num_of_targets=83,
            processing_time=datetime.timedelta(minutes=20),
        )
        return dr

    def _add_repos(self, count: int) -> list[str]:
        fk = Faker()
        list_urls = []
        for _ in range(count):
            dr = self._add_repo(account=fk.word(), repo=fk.word(), fk=fk)
            list_urls.append(f"http://testserver/app/repo/{dr.repo_full_name}")
        return list_urls

    def test_with_repos(self, client, django_assert_num_queries) -> None:
        urls = self._add_repos(200)
        with django_assert_num_queries(2):
            response = client.get("/sitemap.xml")
            assert response.status_code == 200
            assert len(response.context_data["urlset"]) == 200
            locations = {url["location"] for url in response.context_data["urlset"]}
            assert locations == set(urls)

    def test_with_repos_and_excludes(self, client, django_assert_num_queries) -> None:
        fk = Faker()
        self._add_repo(account="cosmo", repo="kramer", fk=fk)
        urls = self._add_repos(30)
        self._add_repo(account="usps", repo="newman", fk=fk)
        with django_assert_num_queries(2):
            response = client.get("/sitemap.xml")
            assert response.status_code == 200
            assert len(response.context_data["urlset"]) == 30
            locations = {url["location"] for url in response.context_data["urlset"]}
            assert locations == set(urls)
