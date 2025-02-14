# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import logging
import re
from urllib.parse import urlparse

import httpx
from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.http import HttpResponseBadRequest, JsonResponse
from django.urls import reverse
from django.views.generic import TemplateView, View

from toolchain.aws.s3 import S3
from toolchain.django.spa.config import StaticContentConfig
from toolchain.pants_demos.depgraph.models import DemoRepo
from toolchain.pants_demos.depgraph.url_names import URLNames
from toolchain.pants_demos.depgraph.utils import get_url_for_repo

_logger = logging.getLogger(__name__)


class RepoSelectionAppView(TemplateView):
    template_name = "pants_demo/repo_selection.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(submit_url=reverse(URLNames.REPO_SELECTION), **kwargs)


class PageNotFoundAppView(TemplateView):
    template_name = "pants_demo/404.html"


class ErrorPageAppView(TemplateView):
    template_name = "pants_demo/error.html"


class TOSPageAppView(TemplateView):
    template_name = "pants_demo/terms.html"


class RepoAppView(TemplateView):
    template_name = "pants_demo/index.html"

    def __init__(self) -> None:
        super().__init__()
        self._static_asset_cfg: StaticContentConfig = settings.STATIC_CONTENT_CONFIG
        scripts_base = staticfiles_storage.url("")
        self._js_bundles = [f"{scripts_base}{bundle}" for bundle in self._static_asset_cfg.bundles]

    def get_context_data(self, **kwargs):
        repo_fn = f"{kwargs['account']}/{kwargs['repo']}"
        context = super().get_context_data(**kwargs)
        scripts_base = staticfiles_storage.url("pants-demo-site/")
        context.update(
            js_bundles=self._js_bundles,
            scripts_base=scripts_base,
            sentry_dsn=settings.JS_SENTRY_DSN,
            disable_indexing=repo_fn in settings.REPOS_DISABLE_INDEXING,
        )
        return context


ACCOUNT_PART = r"(?P<account>[\w\-\_]+)"
REPO_PART = r"(?P<repo>[\w\-\_\.]+)"
REPO_FN_PART = ACCOUNT_PART + "/" + REPO_PART


class RepoSelectionApiView(View):
    # https://stackoverflow.com/a/25102190/38265
    GITHUB_REPO_EXP = re.compile(r"(?P<host>(git@|https://)([\w\.@]+)(/|:))" + REPO_FN_PART + "(.git)?((/)?)")
    SIMPLE_REPO_PATH = re.compile(r"^" + REPO_FN_PART + "$")

    def post(self, request):
        input_repo_url = request.POST.get("repo-url", "").strip()
        if not input_repo_url:
            _logger.warning(f"repo-url not specified: {request.POST}")
            return HttpResponseBadRequest(content="repo-url not specified")
        match = self.GITHUB_REPO_EXP.match(input_repo_url)
        if match:
            match_groups = match.groupdict()
            host = match_groups["host"]
            netloc = host[4:-1] if host.startswith("git@") else urlparse(host).netloc
            account = match_groups["account"]
            repo = match_groups["repo"]
            if repo.lower().endswith(".git"):
                repo = repo[:-4]
            if netloc.lower() not in {"github.com", "www.github.com"}:
                _logger.warning(f"Invalid host {host} ({netloc=})")
                return HttpResponseBadRequest(content="Only GitHub is supported")
        else:
            match = self.SIMPLE_REPO_PATH.match(input_repo_url)
            if not match:
                _logger.warning(f"Invalid repo-url: {input_repo_url}")
                return HttpResponseBadRequest(content="Unsupported repo URL or not a github repo URL")
            match_groups = match.groupdict()
            account = match_groups["account"]
            repo = match_groups["repo"]
        repo_url = f"https://github.com/{account}/{repo}.git".lower()
        _logger.info(f"Check repo: {repo_url}")
        try:
            response = httpx.head(url=repo_url, follow_redirects=True, timeout=3)
        except httpx.RequestError as error:
            _logger.warning(f"Network error on repo validation {repo_url} with github: {error!r}")
            return HttpResponseBadRequest(content="Repo check failed (network error)")
        else:
            if response.status_code != 200:
                _logger.warning(f"Failed to validated repo at {repo_url} with github:  HTTP {response.status_code}")
                return HttpResponseBadRequest(content="Can't access repo on GitHub.com")
        if len(account) > DemoRepo.MAX_SLUG_LENGTH or len(repo) > DemoRepo.MAX_SLUG_LENGTH:
            _logger.warning(f"account or repo too long: {account=} {repo=}")
            return HttpResponseBadRequest(content="This repo is not supported, repo and/or account name are too long.")
        demo_repo = DemoRepo.create(account=account, repo=repo)
        return JsonResponse(_demo_repo_to_json(demo_repo))


class RepoApiView(View):
    def get(self, request, account: str, repo: str):
        demo_repo = DemoRepo.get_or_404(repo_account__iexact=account, repo_name__iexact=repo)
        if demo_repo.is_failed or not demo_repo.is_successful:
            return JsonResponse(_demo_repo_to_json(demo_repo))

        s3 = S3()
        bucket, key = s3.parse_s3_url(demo_repo.result_location)
        # TODO use s3.get_content_or_none() hand handle an error case in a graceful way.
        data = json.loads(s3.get_content(bucket=bucket, key=key))
        return JsonResponse(data)


def _demo_repo_to_json(demo_repo: DemoRepo) -> dict[str, str]:
    json_data = {
        "repo_full_name": demo_repo.repo_full_name,
        "account": demo_repo.repo_account,
        "repo": demo_repo.repo_name,
        "state": demo_repo.processing_state.value,
        "results_url": get_url_for_repo(demo_repo),
    }
    if demo_repo.is_failed:
        json_data["error"] = demo_repo.fail_reason
    return json_data
