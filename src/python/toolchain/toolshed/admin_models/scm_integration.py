# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

from django.contrib.admin import ModelAdmin, display

from toolchain.bitbucket_integration.models import BitbucketAppInstall
from toolchain.django.site.models import Customer
from toolchain.github_integration.models import ConfigureGithubRepo, GithubRepo, GithubRepoStatsConfiguration
from toolchain.toolshed.admin_models.utils import EnumListFilterWithDefault, ReadOnlyModelAdmin
from toolchain.toolshed.admin_models.workflow_utils import WorkflowPayloadMixin, WorkUnitStateFilter

_logger = logging.getLogger(__name__)


class ConfigureGithubRepoModelAdmin(ModelAdmin, WorkflowPayloadMixin):
    list_display = (
        "state",
        "repo_id",
        "created_at",
        "succeeded_at",
        "last_attempt",
        "force_update",
    )
    fields = (
        "repo_id",
        "customer_slug",
        "repo_name",
        "state",
        "created_at",
        "succeeded_at",
        "last_attempt",
        (
            "force_update",
            "_extra_events",
        ),
    )
    list_filter = (WorkUnitStateFilter,)

    def _get_repo(self, obj):
        return GithubRepo.get_or_none(id=obj.repo_id)

    def customer_slug(self, obj):
        customer_id = self._get_repo(obj).customer_id
        return Customer.get_for_id_or_none(customer_id).slug

    def repo_name(self, obj):
        return self._get_repo(obj).name

    def has_add_permission(self, request) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


class GithubRepoStateFilter(EnumListFilterWithDefault):
    title = "active"
    parameter_name = "state"
    default_value = GithubRepo.State.ACTIVE
    default_value_title = "Yes"
    db_field_name = "_repo_state"

    def get_enum_choices(self):
        return ((GithubRepo.State.INACTIVE.value, "No"),)


class GithubRepoModelAdmin(ReadOnlyModelAdmin):
    list_display = (
        "name",
        "is_active",
        "created_at",
        "install_id",
        "repo_id",
        "webhook_id",
    )
    list_filter = (GithubRepoStateFilter,)
    search_fields = ("name",)
    fields = (
        "id",
        "name",
        "state",
        "customer_slug",
        "created_at",
        "repo_id",
        "install_id",
        "webhook_id",
    )

    def get_search_results(self, request, queryset, search_term):
        if search_term:
            customers = Customer.search(search_term)
            if customers:
                _logger.info(f"Found {len(customers)} customers matching {search_term=}")
                return queryset.filter(customer_id__in=[customer.id for customer in customers]), True
        return super().get_search_results(request, queryset, search_term)

    @display(boolean=True)
    def is_active(self, obj: GithubRepo) -> bool:
        return obj.is_active

    def state(self, obj: GithubRepo) -> str:
        return obj.state.value

    def customer_slug(self, obj: GithubRepo) -> str:
        customer = Customer.get_for_id_or_none(customer_id=obj.customer_id, include_inactive=True)
        return customer.slug  # type: ignore[union-attr]


class BitBucketAppInstallStateFilter(EnumListFilterWithDefault):
    title = "installed"
    parameter_name = "state"
    default_value = BitbucketAppInstall.State.INSTALLED
    default_value_title = "Yes"
    db_field_name = "_app_state"

    def get_enum_choices(self):
        return ((BitbucketAppInstall.State.UNINSTALLED.value, "No"),)


class BitbucketAppInstallModelAdmin(ReadOnlyModelAdmin):
    list_display = ("account_name", "installed", "created_at", "last_updated", "account_id")
    list_filter = (BitBucketAppInstallStateFilter,)
    # fields = (("account_name", "account_id", "state"), ("customer_name", "customer_slug"), ("created_at", "last_updated"), ("client_key", ))
    fields = (("account_name", "account_id", "state"), ("created_at", "last_updated"), ("client_key",))

    def state(self, obj) -> str:
        return obj.app_state.value

    @display(boolean=True)
    def installed(self, obj) -> bool:
        return obj.app_state == BitbucketAppInstall.State.INSTALLED

    def _get_customer(self, obj):
        return Customer.objects.get(id=obj.customer_id)

    def customer_name(self, obj) -> str:
        # Never use those in list_display since they will do a DB roundtrip for every row
        return self._get_customer(obj).name

    def customer_slug(self, obj) -> str:
        # Never use those in list_display since they will do a DB roundtrip for every row
        return self._get_customer(obj).slug


def get_scm_integration_models():
    return {
        ConfigureGithubRepo: ConfigureGithubRepoModelAdmin,
        GithubRepo: GithubRepoModelAdmin,
        BitbucketAppInstall: BitbucketAppInstallModelAdmin,
        GithubRepoStatsConfiguration: ReadOnlyModelAdmin,
    }
