# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, unique

from sentry_sdk import push_scope

from toolchain.django.site.models import Customer, Repo, RepoCreationError
from toolchain.github_integration.common.records import GitHubEvent
from toolchain.github_integration.models import ConfigureGithubRepo, GithubRepo

_logger = logging.getLogger(__name__)

# https://docs.github.com/developers/webhooks-and-events/webhooks/webhook-events-and-payloads?actionType=unsuspend#installation
# https://docs.github.com/developers/webhooks-and-events/webhooks/webhook-events-and-payloads?actionType=suspend#installation
# https://docs.github.com/developers/webhooks-and-events/webhooks/webhook-events-and-payloads?actionType=new_permissions_accepted#installation
_INGORED_INSTALL_ACTIONS = frozenset(["unsuspend", "suspend", "new_permissions_accepted"])


@unique
class GithubAccountType(Enum):
    ORG = "Organization"
    USER = "User"


@dataclass(frozen=True)
class Installation:
    install_id: str
    owner: str
    org_logo_url: str
    account_type: str
    action: str

    @classmethod
    def from_payload(cls, payload: dict) -> Installation:
        install_json = payload["installation"]
        account = install_json["account"]

        return cls(
            install_id=str(install_json["id"]),
            owner=account["login"],
            org_logo_url=account["avatar_url"],
            account_type=account["type"],
            action=payload["action"],
        )

    @property
    def is_github_org(self) -> bool:
        return self.account_type == GithubAccountType.ORG.value

    @property
    def is_creation_action(self) -> bool:
        return self.action == "created"

    @property
    def is_deletion_action(self) -> bool:
        return self.action == "deleted"


def _get_customer(installation: Installation) -> Customer | None:
    customer = Customer.for_slug(slug=installation.owner, include_inactive=True)
    if customer and not customer.is_active:
        _logger.warning(f"add_repo_for_install for inactive customer {customer=} {installation}")
        return None
    if customer:
        customer.maybe_set_logo(installation.org_logo_url)
        return customer
    if not installation.is_github_org:
        _logger.warning(f"add_repo_for_install missing customer non Github org: {installation}")
        return None
    _logger.info(f"self service onboarding disabled. {installation}")
    return None
    # _logger.info(f"add_repo_for_install missing customer for {installation}")
    # # Hacky, but the webhook payload doesn't have org name.
    # org_info = get_github_org_info(slug=installation.owner)
    # return Customer.create(
    #     slug=installation.owner,
    #     name=org_info.name,
    #     scm=Customer.Scm.GITHUB,
    #     customer_type=Customer.Type.PROSPECT,
    #     logo_url=installation.org_logo_url,
    # )


def _add_repos(installation: Installation, repos_json: list[dict]) -> list[GithubRepo]:
    customer = _get_customer(installation)
    if not customer:
        return []
    github_repos: list[GithubRepo] = []
    for repo_json in repos_json:
        gh_repo = _add_repo(customer=customer, install_id=installation.install_id, repo_json=repo_json)
        if gh_repo:
            github_repos.append(gh_repo)
    return github_repos


def _add_repo(customer: Customer, install_id: str, repo_json: dict) -> GithubRepo | None:
    full_name = repo_json["full_name"]
    name = repo_json["name"]
    repo_id = str(repo_json["id"])
    try:
        Repo.create(slug=name, customer=customer, name=full_name)
    except RepoCreationError as error:
        _logger.warning(f"Failed to create repo: {error!r}", exc_info=True)
        return None
    return GithubRepo.activate_or_create(
        repo_id=repo_id, install_id=install_id, repo_name=name, customer_id=customer.pk
    )


def _delete_all_installation_repos(installation: Installation) -> list[GithubRepo]:
    customer = Customer.for_slug(slug=installation.owner)
    if not customer:
        _logger.warning(f"delete_all_installation_repos missing customer for {installation}")
        return []
    deactivated_repos = []
    for repo in GithubRepo.get_for_installation(customer_id=customer.pk, install_id=installation.install_id):
        if repo.deactivate():
            deactivated_repos.append(repo)
    return deactivated_repos


def _deactivate_repos(installation: Installation, repos_json: list[dict]) -> list[GithubRepo]:
    deactivated_repos = []
    for repo_json in repos_json:
        repo_id = str(repo_json["id"])
        repo = GithubRepo.get_by_github_repo_id(repo_id=repo_id)
        if not repo:
            _logger.warning(f"Unknown repo={repo_json['name']} {repo_id=}")
            continue
        if repo.install_id != installation.install_id:
            _logger.warning(
                f"not deactivating repo={repo_json['name']} {repo_id=} unexpected intall id (got={repo.install_id} expected={installation.install_id})"
            )
            continue
        if repo.deactivate():
            deactivated_repos.append(repo)
    return deactivated_repos


def _app_installation_event_handler(github_event: GitHubEvent) -> bool:
    # https://developer.github.com/v3/activity/events/types/#installationevent
    data = github_event.json_payload
    installation = Installation.from_payload(data)
    if installation.action in _INGORED_INSTALL_ACTIONS:
        _logger.info(f"Ignored {installation.action} for {installation.owner} ({installation.account_type})")
        return False
    # Not handling new_permissions_accepted (currently)
    if installation.is_creation_action:
        # Docs say repositories should be in this event, but I have observed it is missing when action is "deleted"
        repos = data["repositories"]
        repos_added = _add_repos(installation, repos)
        ConfigureGithubRepo.bulk_create(repos_added)
        return bool(repos_added)
    if installation.is_deletion_action:
        repos_removed = _delete_all_installation_repos(installation)
        return bool(repos_removed)

    with push_scope() as scope:
        # This tells sentry to group all events from this message into a single issue.
        scope.fingerprint = ["github_integration", "app_install", "unkown_action"]
        _logger.error(f"unknown install action: {installation.action} from {installation.owner=}")
    return False


def _repo_installation_event_handler(github_event: GitHubEvent) -> bool:
    # https://developer.github.com/v3/activity/events/types/#installationrepositoriesevent
    data = github_event.json_payload
    installation = Installation.from_payload(data)
    added_repos = data["repositories_added"]
    removed_repos = data["repositories_removed"]
    added = _add_repos(installation, added_repos) if added_repos else []
    removed = _deactivate_repos(installation, removed_repos) if removed_repos else []
    ConfigureGithubRepo.bulk_create(added + removed)
    return bool(added or removed)


def _handle_app_authorization(github_event: GitHubEvent) -> bool:
    payload = github_event.json_payload
    sender = payload["sender"]
    action = payload["action"]
    account = sender["login"]
    account_id = sender["id"]
    account_type = sender["type"]
    account_desc = f"{action=} {account=} (id={account_id}) type={account_type}"
    customer = Customer.for_slug(slug=account)
    if not customer:
        _logger.warning(f"no customer match for {account_desc}")
        return False
    if customer.scm_provider != Customer.Scm.GITHUB or account_type != GithubAccountType.ORG.value:
        _logger.warning(f"Unexpected customer account via github_app_authorization event {account_desc}")
        return False
    # TODO: do something with in this case. TBD what
    _logger.info(f"customer match for {account_desc} {customer=}")
    return True


APP_EVENT_HANDLERS = {
    # Deprecated: integration_installation and integration_installation_repositories
    # https://developer.github.com/webhooks/#events
    "installation": _app_installation_event_handler,
    "installation_repositories": _repo_installation_event_handler,
    # https://docs.github.com/en/developers/webhooks-and-events/webhooks/webhook-events-and-payloads#github_app_authorization
    "github_app_authorization": _handle_app_authorization,
}


def handle_github_app_event(github_event: GitHubEvent) -> bool:
    handler = APP_EVENT_HANDLERS.get(github_event.event_type)
    handled = handler(github_event) if handler else False
    _logger.info(
        f"GitHub App Webhook event={github_event.event_type} handled={handled}: {github_event.json_payload!r}."
    )
    return handled
