# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from typing import Callable
from urllib.parse import urljoin

from django.conf import settings
from django.http import Http404
from rest_framework.response import Response
from rest_framework.views import APIView

from toolchain.django.site.models import Customer, Repo
from toolchain.github_integration.api.constants import CIChecksResults
from toolchain.github_integration.api.exceptions import CIResolveError
from toolchain.github_integration.api.github_actions_checks import check_github_actions_build
from toolchain.github_integration.common.records import GitHubEvent
from toolchain.github_integration.hook_handlers.app_handlers import handle_github_app_event
from toolchain.github_integration.hook_handlers.repo_handlers import handle_github_repo_event
from toolchain.github_integration.models import GithubRepo
from toolchain.github_integration.repo_data_store import GithubRepoDataStore

_logger = logging.getLogger(__name__)


class BaseGithubIntegrationView(APIView):
    view_type = "internal"


class BaseInternalApiView(BaseGithubIntegrationView):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        repo_id = kwargs["repo_id"]
        customer_id = kwargs["customer_id"]
        self.repo = Repo.get_by_id_or_404(customer_id=customer_id, repo_id=repo_id)
        self.github_repo = GithubRepo.get_for_customer_and_slug(customer_id=customer_id, repo_slug=self.repo.slug)
        if not self.github_repo:
            _logger.warning(f"No GithubRepo for {self.repo} when accessing {request.method} {request.path}")
            raise Http404
        self.store = GithubRepoDataStore(customer_id=customer_id, repo_id=repo_id)


class PullRequestView(BaseInternalApiView):
    def get(self, request, customer_id: str, repo_id: str, pr_number: int):
        pr_data = self.store.get_pull_request_data(str(pr_number))
        if pr_data is None:
            raise Http404
        return Response({"pull_request_data": pr_data})


class CommitsView(BaseInternalApiView):
    def get(self, request, customer_id: str, repo_id: str, ref_name: str, commit_sha: str):
        commit_data = self.store.get_push_data(ref_name=ref_name, commit_sha=commit_sha)
        if commit_data is None:
            raise Http404
        return Response({"commit_data": commit_data["head_commit"]})


class PushView(BaseInternalApiView):
    def get(self, request, customer_id: str, repo_id: str, ref_name: str, commit_sha: str):
        push_data = self.store.get_push_data(ref_name=ref_name, commit_sha=commit_sha)
        if push_data is None:
            raise Http404
        del push_data["organization"]
        del push_data["repository"]
        return Response({"push_data": push_data})


class RepoWebhookView(BaseGithubIntegrationView):
    def get(self, request, github_repo_id: str):
        github_repo = GithubRepo.get_by_github_repo_id(repo_id=github_repo_id)
        if not github_repo:
            raise Http404
        if not github_repo.webhooks_secret:
            _logger.warning(f"No secret for {github_repo=}")
            raise Http404()
        return Response(data={"repo": {"name": github_repo.name, "secret": github_repo.webhooks_secret}})

    def post(self, request, github_repo_id: str):
        event = GitHubEvent.from_json(request.data)
        handled = handle_github_repo_event(event)
        return Response(status=201 if handled else 200, data={"handled": handled})


class AppWebhookView(BaseGithubIntegrationView):
    def post(self, request):
        event = GitHubEvent.from_json(request.data)
        handled = handle_github_app_event(event)
        return Response(status=201 if handled else 200, data={"handled": handled})


class CIResolveView(BaseGithubIntegrationView):
    MAX_KEY_LENGTH = 48  # Must match RestrictedAccessToken.ci_build_key fields size

    def post(self, request, customer_id: str, repo_id: str):
        ci_env_vars: dict[str, str] = request.data["ci_env"]
        started_treshold = datetime.timedelta(seconds=request.data["started_treshold_sec"])
        repo = Repo.get_by_id_or_404(customer_id=customer_id, repo_id=repo_id)
        github_repo = GithubRepo.get_for_customer_and_slug(customer_id=repo.customer_id, repo_slug=repo.slug)
        if not github_repo:
            _logger.warning(f"No GithubRepo for {repo}")
            return Response(data={"error": f"No GithubRepo for {repo.slug}"}, status=401)

        checker_func = _get_checker(ci_env_vars)
        if not checker_func:
            _logger.warning(f"Unknown CI system. {ci_env_vars=}")
            return Response(data={"error": "Unknown CI system"}, status=400)
        try:
            result = checker_func(repo=repo, ci_env_vars=ci_env_vars, start_threshold=started_treshold)  # type: ignore[call-arg]
        except CIResolveError as error:
            _logger.warning(f"ci_check_failed: {error!r} context={ci_env_vars}")
            return Response(data={"error": str(error)}, status=401)

        store = GithubRepoDataStore.for_repo(repo)
        pr_info = store.get_pull_request_data(result.pull_request_number)  # type: ignore[arg-type]
        if not pr_info:
            _logger.warning(f"Can't find PR data from GitHub: {result.pull_request_number=} {repo=}")
            return Response(data={"error": f"ci={result.ci_type} Missing PR info"}, status=401)
        if len(result.build_key) > self.MAX_KEY_LENGTH:
            _logger.warning(f"CI build key to long: {result.build_key}")
            return Response(data={"error": "Invalid build key"}, status=401)
        data = {
            "labels": pr_info["labels"],
            "user_id": pr_info["user"]["id"],
            "key": result.build_key,
            "pr_number": result.pull_request_number,
            "ci_link": result.job_link,
        }
        return Response(data=data)


def _get_checker(ci_env_vars) -> Callable[[Repo, dict[str, str], datetime.timedelta], CIChecksResults] | None:
    if ci_env_vars.get("GITHUB_ACTIONS") == "true":
        return check_github_actions_build
    return None


class CustomerRepoView(BaseGithubIntegrationView):
    def options(self, request, customer_id: str):
        app_link = settings.GITHUB_CONFIG.public_link
        customer = Customer.get_for_id_or_none(customer_id)
        if not customer:
            _logger.warning(f"No customer with {customer_id=}")
            raise Http404
        # https://github.com/organizations/toolchainlabs/settings/installations/1141606
        data = {"install_link": urljoin(app_link, "installations/new")}
        install_id = GithubRepo.get_install_id_for_customer_id(customer_id)
        if install_id:
            data.update(
                install_id=install_id,
                configure_link=f"https://github.com/organizations/{customer.slug}/settings/installations/{install_id}",
            )
        return Response({"data": data})

    def get(self, request, customer_id: str):
        gh_repos = GithubRepo.get_for_customer_id(customer_id)
        repos_json = []
        for gh_repo in gh_repos:
            repos_json.append(
                {
                    "created_at": gh_repo.created_at.isoformat(),
                    "name": gh_repo.name,
                    "state": gh_repo.state.value,
                    "repo_id": gh_repo.repo_id,  # the GH ID
                }
            )
        return Response({"results": repos_json})
