# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import copy
import logging

from django.contrib.admin import ModelAdmin, SimpleListFilter, TabularInline, display
from django.contrib.admin.options import IncorrectLookupParameters
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group, Permission, User
from django.db.models import OuterRef, Subquery
from django.forms import ModelChoiceField, TypedMultipleChoiceField
from django.http import HttpRequest
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.auth.constants import AccessTokenAudience
from toolchain.django.site.models import (
    AccessTokenState,
    AccessTokenUsage,
    AllocatedRefreshToken,
    Customer,
    CustomerUser,
    Repo,
    ToolchainUser,
)
from toolchain.toolshed.admin_models.utils import (
    EnumListFilterWithDefault,
    ReadOnlyModelAdmin,
    get_customer_str,
    get_link_to_customer,
    get_link_to_user,
    pretty_format_json,
)
from toolchain.toolshed.url_names import URLNames
from toolchain.users.constants import CURRENT_TOS_VERSION
from toolchain.users.models import (
    AccessTokenExchangeCode,
    AuthProvider,
    GithubRepoConfig,
    ImpersonationAuditLog,
    ImpersonationSession,
    PeriodicallyCheckAccessTokens,
    PeriodicallyExportCustomers,
    PeriodicallyExportRemoteWorkerTokens,
    PeriodicallyNotifyExpringTokens,
    PeriodicallyRevokeTokens,
    RemoteExecWorkerToken,
    RestrictedAccessToken,
    UserAuth,
    UserCustomerAccessConfig,
    UserTermsOfServiceAcceptance,
)
from toolchain.users.ui.impersonation_util import user_can_be_impersonated

_logger = logging.getLogger(__name__)


class CustomerUserInline(TabularInline):
    model = CustomerUser
    extra = 1


def _modify_fieldsets(orig_fieldsets):
    fieldsets = copy.deepcopy(orig_fieldsets)
    # We assert that the original fieldsets have the "Personal info" section where we expect it, just to be safe.
    ps_info = fieldsets[1]
    if ps_info[0] != _("Personal info"):
        raise ToolchainAssertion("The 'personal info' section wasn't where we expected it in the UserAdmin fieldsets.")
    ps_info[1]["fields"] = ("full_name", "email", "avatar_url")
    fieldsets[0][1]["fields"] = ("username", "api_id")
    fieldsets[2][1]["fields"] = (
        "is_active",
        "is_staff",
    )
    return fieldsets


class UserStateFilter(SimpleListFilter):
    title = "active"
    parameter_name = "state"

    def lookups(self, request, model_admin):
        return ((None, "Yes"), ("no", "No"), ("all", "All"))

    def choices(self, changelist):
        for lookup, title in self.lookup_choices:
            yield {
                "selected": self.value() == lookup,
                "query_string": changelist.get_query_string({self.parameter_name: lookup}, []),
                "display": title,
            }

    def queryset(self, request, queryset):
        value = self.value()
        if value is None:
            return queryset.filter(is_active=True)
        if value == "all":
            return queryset
        if value == "no":
            return queryset.filter(is_active=False)
        raise IncorrectLookupParameters(f"Invalid queryset filter value: {value}")


class ToolchainUserAdmin(UserAdmin):
    MAX_CUSTOMERS = 5
    fieldsets = _modify_fieldsets(UserAdmin.fieldsets)
    exclude = ("customers",)
    inlines = (CustomerUserInline,)
    ordering = ("-last_login",)
    list_filter = (UserStateFilter, "is_staff")
    list_display = (
        "username",
        "email",
        "name",
        "user_actions",
        "is_active",
        "is_staff",
        "last_login",
        "date_joined",
        "customers_slugs",
        "api_id",
    )
    actions = ("deactivate_users", "activate_users")
    readonly_fields = ("last_login", "date_joined", "api_id", "user_actions")

    def name(self, obj) -> str:
        return obj.get_full_name()

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("customers")

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    def customers_slugs(self, obj) -> list[str]:
        customers = obj.customers.all()[:5]
        return [customer.slug for customer in customers]

    def deactivate_users(self, request, queryset):
        count = queryset.filter(is_active=True).update(is_active=False, is_staff=False)
        self.message_user(request, f"{count} successfully deactivated.")

    def activate_users(self, request, queryset):
        count = queryset.filter(is_active=False).update(is_active=True, is_staff=False)
        self.message_user(request, f"{count} successfully activated.")

    def user_actions(self, user: ToolchainUser):
        if not user_can_be_impersonated(user):
            return ""

        return format_html(
            """
                <a class="button" href="{}">Impersonate</a>
            """,
            reverse(URLNames.REQUEST_UI_IMPERSONATION, args=[user.api_id]),
        )

    deactivate_users.short_description = "Deactivate users"  # type: ignore
    activate_users.short_description = "Activate users"  # type: ignore

    def get_object(self, request: HttpRequest, object_id: str, from_field: str | None = None) -> ToolchainUser | None:
        if object_id.isnumeric():
            return super().get_object(request, object_id, from_field)
        _logger.info(f"Lookup user by API ID: {object_id}")
        return ToolchainUser.get_by_api_id(api_id=object_id, include_inactive=True)


class CustomerStateFilter(EnumListFilterWithDefault):
    title = "active"
    parameter_name = "state"
    default_value = Customer.State.ACTIVE
    default_value_title = "Yes"
    db_field_name = "_customer_state"

    def get_enum_choices(self):
        return ((Customer.State.INACTIVE.value, "No"),)


class CustomerTypeFilter(SimpleListFilter):
    title = "type"
    parameter_name = "type"

    def lookups(self, request, model_admin):
        return get_enum_filter_lookup(Customer.Type, modifer=lambda member: member.value.capitalize())

    def queryset(self, request, queryset):
        customer_type = self.value()
        if customer_type:
            return queryset.filter(_customer_type=customer_type)
        return queryset


class CustomerServiceLevelFilter(SimpleListFilter):
    title = "Service level"
    parameter_name = "service_level"

    def lookups(self, request, model_admin):
        return get_enum_filter_lookup(Customer.ServiceLevel, modifer=lambda member: member.value.capitalize())

    def queryset(self, request, queryset):
        service_level = self.value()
        if service_level:
            return queryset.filter(_service_level=service_level)
        return queryset


class CustomerAdmin(ModelAdmin):
    exclude = ("users",)
    inlines = (CustomerUserInline,)
    list_display = ("slug", "name", "scm", "is_active", "created_at", "customer_type", "service_level", "id")
    list_filter = (CustomerStateFilter, CustomerTypeFilter, CustomerServiceLevelFilter)
    readonly_fields = ("id",)
    search_fields = ("slug", "name", "id")

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    def scm(self, obj: Customer) -> str:
        return obj.scm_provider.value

    def customer_type(self, obj: Customer) -> str:
        return obj.customer_type.value.capitalize()

    def service_level(self, obj: Customer) -> str:
        return obj.service_level.value.replace("_", " ").capitalize()

    @display(boolean=True)
    def is_active(self, obj) -> bool:
        return obj.is_active


class RepoStateFilter(EnumListFilterWithDefault):
    title = "active"
    parameter_name = "state"
    default_value = Repo.State.ACTIVE
    default_value_title = "Yes"
    db_field_name = "_repo_state"

    def get_enum_choices(self):
        return ((Repo.State.INACTIVE.value, "No"),)


class RepoVisibilityFilter(SimpleListFilter):
    title = "visibility"
    parameter_name = "visibility"

    def lookups(self, request, model_admin):
        return get_enum_filter_lookup(Repo.Visibility, modifer=lambda member: member.value.capitalize())

    def queryset(self, request, queryset):
        visibility = self.value()
        if visibility:
            return queryset.filter(_visibility=visibility)
        return queryset


class RepoAdmin(ModelAdmin):
    list_display = ("slug", "name", "customer_str", "is_active", "created_at", "is_public", "id")
    search_fields = ("slug", "name")
    readonly_fields = ("id",)
    list_filter = (RepoStateFilter, RepoVisibilityFilter)

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("customer")

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ("customer",)
        return self.readonly_fields

    @display(description="customer")
    def customer_str(self, obj) -> str:
        return get_customer_str(obj.customer)

    @display(boolean=True)
    def is_active(self, obj) -> bool:
        return obj.is_active

    @display(boolean=True)
    def is_public(self, obj) -> bool:
        return obj.visibility == Repo.Visibility.PUBLIC


def _annotate_username(qs, fieldname: str = "_username", api_id: str = "user_api_id"):
    user_ref = ToolchainUser.objects.filter(api_id=OuterRef(api_id))
    annotations = {fieldname: Subquery(user_ref.values("username"))}
    return qs.annotate(**annotations)


class AccessTokenExchangeCodeAdmin(ReadOnlyModelAdmin):
    list_display = (
        "username",
        "repo",
        "state",
        "created_at",
        "code",
    )
    date_hierarchy = "created_at"
    fields = ("created_at", "state", "code", ("username", "user_api_id"), ("repo", "repo_id"))

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = _annotate_username(qs)
        repo_ref = Repo.objects.filter(id=OuterRef("repo_id"))
        return qs.annotate(_repo_slug=Subquery(repo_ref.values("slug")))

    def username(self, obj) -> str:
        return obj._username

    def repo(self, obj) -> str:
        return obj._repo_slug

    def state(self, obj) -> str:
        return obj.state.value.capitalize()


def get_enum_filter_lookup(enum_cls, modifer) -> tuple[tuple[str, str], ...]:
    return tuple((member.value, modifer(member)) for member in enum_cls)


class AccessTokenStateFilter(SimpleListFilter):
    title = "active"
    parameter_name = "state"

    def lookups(self, request, model_admin):
        return get_enum_filter_lookup(AccessTokenState, modifer=lambda member: member.value.capitalize())

    def queryset(self, request, queryset):
        state = self.value()
        if state:
            return queryset.filter(_token_state=state)
        return queryset


class AccessTokenUsageFilter(SimpleListFilter):
    title = "usage"
    parameter_name = "usage"

    def lookups(self, request, model_admin):
        return get_enum_filter_lookup(AccessTokenUsage, modifer=lambda member: member.value.upper())

    def queryset(self, request, queryset):
        state = self.value()
        if state:
            return queryset.filter(_usage=state)
        return queryset


def revoke_tokens(modeladmin, request, queryset):
    for token in queryset:
        token.revoke()


revoke_tokens.short_description = "Revoke tokens"  # type: ignore[attr-defined]


class AllocatedRefreshTokensAdmin(ModelAdmin):
    list_display = (
        "username",
        "id",
        "state",
        "usage",
        "issued_at",
        "last_seen",
        "expires_at",
        "description",
        "customer_name",
        "repo_name",
    )
    list_filter = (AccessTokenStateFilter, AccessTokenUsageFilter)
    fields = (
        "id",
        "username",
        "state",
        "usage",
        ("issued_at", "last_seen", "expires_at"),
        ("description", "audiences"),
        ("repo_name", "repo_id", "customer_id", "customer_name"),
    )
    readonly_fields = (
        "id",
        "username",
        "state",
        "usage",
        "issued_at",
        "last_seen",
        "expires_at",
        "repo_name",
        "repo_id",
        "audiences",
        "customer_id",
        "customer_name",
    )
    actions = (revoke_tokens,)

    search_fields = ("id",)

    def get_search_results(self, request, queryset, search_term):
        if search_term:
            users = ToolchainUser.search(search_term)
            if users:
                _logger.info(f"Found {len(users)} users matching {search_term=}")
                return queryset.filter(user_api_id__in=[user.api_id for user in users]), True
        return super().get_search_results(request, queryset, search_term)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = _annotate_username(qs)
        repo_ref = Repo.objects.filter(id=OuterRef("repo_id"))
        customer_ref = Customer.objects.filter(id=OuterRef("_customer_id"))
        return qs.annotate(
            _repo_name=Subquery(repo_ref.values("name")),
            _customer_id=Subquery(repo_ref.values("customer_id")),
            _customer_name=Subquery(customer_ref.values("name")),
        )

    def repo_name(self, obj) -> str:
        return obj._repo_name if obj.repo_id else "N/A"

    def customer_id(self, obj) -> str:
        return obj._customer_id if obj.repo_id else "N/A"

    def customer_name(self, obj) -> str:
        return obj._customer_name if obj.repo_id else "N/A"

    def audiences(self, obj) -> str:
        return obj.audiences.to_display()

    def username(self, obj) -> str:
        return obj._username

    def state(self, obj) -> str:
        return obj.state.value.capitalize()

    def usage(self, obj) -> str:
        return obj.usage.value.upper()

    def has_add_permission(self, request) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


class GithubRepoConfigAdmin(ModelAdmin):
    list_display = ("repo_slug", "repo_name", "max_build_tokens", "started_treshold", "token_ttl")
    readonly_fields = ("repo_slug", "repo_name")
    fields = (("repo_id", "repo_slug", "repo_name"), "max_build_tokens", "started_treshold_sec", "token_ttl_sec")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        repo_ref = Repo.objects.filter(id=OuterRef("repo_id"))
        return qs.annotate(_repo_slug=Subquery(repo_ref.values("slug")), _repo_name=Subquery(repo_ref.values("name")))

    def repo_name(self, obj) -> str:
        return obj._repo_name

    def repo_slug(self, obj) -> str:
        return obj._repo_slug


class LooseModelChoiceField(ModelChoiceField):
    def to_python(self, value):
        return value


class CustomerSelectionChoiceField(LooseModelChoiceField):
    def __init__(self) -> None:
        super().__init__(label="Customer", queryset=Customer.base_qs(), to_field_name="id")

    def label_from_instance(self, customer: Customer) -> str:
        return get_customer_str(customer)


class EnumListChoiceField(TypedMultipleChoiceField):
    def _coerce(self, value) -> str:
        return ",".join(value)


def _maybe_add_user_lookup(db_field) -> LooseModelChoiceField | None:
    if db_field.name != "user_api_id":
        return None
    return LooseModelChoiceField(
        label="User",
        queryset=ToolchainUser.active_users(),
        to_field_name="api_id",
    )


class ImpersonationAuditLogInline(TabularInline):
    model = ImpersonationAuditLog
    ordering = ("created_at",)
    readonly_fields = (
        "created_at",
        "path",
        "method",
        "data_",
    )

    def has_add_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def data_(self, obj):
        """Displays the data field as a formatted object so that it's easier to read through the audit log."""
        return pretty_format_json(obj.data)


class ImpersonationSessionAdmin(ReadOnlyModelAdmin):
    list_display = ("id", "user", "impersonator", "created_at", "expires_at", "started")
    fields = ("id", "user", "impersonator", "created_at", "expires_at", "started")
    inlines = [ImpersonationAuditLogInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = _annotate_username(qs, "_user", "user_api_id")
        qs = _annotate_username(qs, "_impersonator", "impersonator_api_id")

        return qs

    def user(self, obj) -> str:
        return obj._user

    def impersonator(self, obj) -> str:
        return obj._impersonator


class UserCustomerAccessConfigAdmin(ModelAdmin):
    list_display = ("username", "customer", "is_org_admin", "allowed_audiences", "user_link", "customer_link")
    fields = (
        ("user_api_id", "username"),
        ("customer_id", "customer", "_role"),
        "currently_allowed",
        "_allowed_audiences",
    )

    readonly_fields = ("username", "customer", "currently_allowed")
    search_fields = ("id",)  # dummy since we override get_search_results

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user_ref = ToolchainUser.objects.filter(api_id=OuterRef("user_api_id"))
        customer_ref = Customer.objects.filter(id=OuterRef("customer_id"))
        return qs.annotate(
            _username=Subquery(user_ref.values("username")), _customer_slug=Subquery(customer_ref.values("slug"))
        )

    @display(description="User")
    def user_link(self, obj) -> str:
        return get_link_to_user(obj.user_api_id)

    @display(description="Customer")
    def customer_link(self, obj) -> str:
        return get_link_to_customer(obj.customer_id, display=self.customer(obj))

    def username(self, obj) -> str:
        return obj._username

    def customer(self, obj) -> str:
        return obj._customer_slug

    def currently_allowed(self, obj) -> str:
        return obj.allowed_audiences.to_display()

    @display(boolean=True)
    def is_org_admin(self, obj) -> bool:
        return obj.is_admin

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj=obj, change=change, **kwargs)
        form.base_fields[
            "_role"
        ].help_text = "This value will be overridden when the user logs in based on the user's Github permissions"
        form.base_fields["_allowed_audiences"].help_text = "Use ⌘ (cmd) + option + click to select multiple."
        return form

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ("user_api_id", "customer_id")
        return self.readonly_fields

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        form_field = _maybe_add_user_lookup(db_field)
        if form_field:
            return form_field

        if db_field.name == "customer_id":
            return CustomerSelectionChoiceField()
        if db_field.name == "_allowed_audiences":
            return EnumListChoiceField(
                choices=[(val.api_name, val.name) for val in AccessTokenAudience],
                label="Allowed Audiences",
            )
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def get_search_results(self, request, queryset, search_term):
        if search_term:
            users = ToolchainUser.search(search_term)
            if users:
                _logger.info(f"Found {len(users)} users matching {search_term=}")
                return queryset.filter(user_api_id__in=[user.api_id for user in users]), True
            else:
                customers = Customer.search(search_term)
                if customers:
                    _logger.info(f"Found {len(customers)} customers matching {search_term=}")
                return queryset.filter(customer_id__in=[customer.id for customer in customers]), True

        return super().get_search_results(request, queryset, search_term)


class AuthProviderFilter(SimpleListFilter):
    title = "provider"
    parameter_name = "provider"

    def lookups(self, request, model_admin):
        return get_enum_filter_lookup(AuthProvider, modifer=lambda member: member.value.capitalize())

    def queryset(self, request, queryset):
        provider = self.value()
        if provider:
            return queryset.filter(_provider=provider)
        return queryset


class UserAuthAdmin(ModelAdmin):
    list_display = ("user", "provider", "user_id", "username", "user_api_id")
    fields = (("user_api_id", "user"), ("provider", "user_id", "username"), "email_addresses", ("created", "modified"))
    readonly_fields = ("created", "modified", "user_id", "email_addresses", "provider", "user")
    list_filter = (AuthProviderFilter,)
    search_fields = ("username", "user_id")

    def has_add_permission(self, request) -> bool:
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return _annotate_username(qs, fieldname="_tc_user")

    def user(self, obj) -> str:
        return obj._tc_user

    def provider(self, obj: UserAuth) -> str:
        return obj.provider.value

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        form_field = _maybe_add_user_lookup(db_field)
        if form_field:
            return form_field
        return super().formfield_for_dbfield(db_field, request, **kwargs)


class UserTermsOfServiceAcceptanceAdmin(ReadOnlyModelAdmin):
    change_list_template = "admin/tos_acceptance_changelist.html"
    list_display = ("user", "created", "email", "client_ip", "request_id", "user_api_id")
    search_fields = ("username", "user_id")
    fields = (("user", "email", "user_api_id"), ("created", "client_ip", "request_id"))
    readonly_fields = ("created", "email", "client_ip", "request_id", "user_api_id")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return _annotate_username(qs, fieldname="_tc_user")

    def user(self, obj) -> str:
        return obj._tc_user

    def _get_tos_compliance(self):
        active_users_qs = ToolchainUser.active_users()
        tos_qs = UserTermsOfServiceAcceptance.objects.filter(
            tos_version=CURRENT_TOS_VERSION, user_api_id__in=Subquery(active_users_qs.values_list("api_id"))
        )
        user_count = active_users_qs.count()
        tos_accepted_count = tos_qs.count()
        return {
            "tos_version": CURRENT_TOS_VERSION,
            "compliance": f"{tos_accepted_count/user_count:.0%}",
            "users_count": user_count,
            "tos_accepted_count": tos_accepted_count,
        }

    def changelist_view(self, request, extra_context=None):
        ec = self._get_tos_compliance()
        ec.update(extra_context or {})
        return super().changelist_view(request, extra_context=ec)


def get_user_models():
    return {
        ToolchainUser: ToolchainUserAdmin,
        Repo: RepoAdmin,
        Customer: CustomerAdmin,
        CustomerUser: False,
        GithubRepoConfig: GithubRepoConfigAdmin,
        ImpersonationAuditLog: False,
        ImpersonationSession: ImpersonationSessionAdmin,
        User: False,
        Group: False,
        Permission: False,
        AccessTokenExchangeCode: AccessTokenExchangeCodeAdmin,
        AllocatedRefreshToken: AllocatedRefreshTokensAdmin,
        UserAuth: UserAuthAdmin,
        UserCustomerAccessConfig: UserCustomerAccessConfigAdmin,
        UserTermsOfServiceAcceptance: UserTermsOfServiceAcceptanceAdmin,
        # Default admin UI for now, still needs to be customized.
        RestrictedAccessToken: ReadOnlyModelAdmin,
        PeriodicallyRevokeTokens: ReadOnlyModelAdmin,
        PeriodicallyCheckAccessTokens: ReadOnlyModelAdmin,
        PeriodicallyExportCustomers: ReadOnlyModelAdmin,
        PeriodicallyNotifyExpringTokens: ReadOnlyModelAdmin,
        RemoteExecWorkerToken: ReadOnlyModelAdmin,
        PeriodicallyExportRemoteWorkerTokens: ReadOnlyModelAdmin,
    }
