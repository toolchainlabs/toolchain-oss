# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from collections import OrderedDict
from collections.abc import Sequence
from urllib.parse import urlparse

from django.conf import settings
from django.core.validators import RegexValidator
from django.forms import CharField
from django.http import Http404, HttpResponseBadRequest
from django.urls import reverse
from humanize.filesize import naturalsize
from rest_framework import exceptions
from rest_framework.decorators import action
from rest_framework.exceptions import ErrorDetail, NotFound, ParseError, ValidationError
from rest_framework.fields import empty
from rest_framework.metadata import BaseMetadata
from rest_framework.mixins import UpdateModelMixin
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.serializers import ModelSerializer, PrimaryKeyRelatedField
from rest_framework.status import HTTP_404_NOT_FOUND
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from toolchain.base.datetime_tools import utcnow
from toolchain.django.auth.constants import AccessTokenAudience
from toolchain.django.forms.base_form import ToolchainForm
from toolchain.django.site.models import AllocatedRefreshToken, Customer, Repo, ToolchainUser
from toolchain.django.site.utils.pagination_api import ToolchainSlugCursorPagination
from toolchain.github_integration.client.repo_clients import GithubCustomerReposClient
from toolchain.payments.client.customer_client import PaymentsCustomerClient
from toolchain.payments.stripe_integration.client.customer_client import StripeCustomerClient
from toolchain.users.jwt.authentication import AuthenticationFromInternalHeaders
from toolchain.users.jwt.permissions import AccessTokensPermissions
from toolchain.users.models import RemoteExecWorkerToken, UserAuth, UserCustomerAccessConfig
from toolchain.users.url_names import URLNames

_logger = logging.getLogger(__name__)
USE_REQUEST_USER_ARG = "me"


class BaseUserApiView(APIView):
    view_type = "app"
    audience = AccessTokenAudience.FRONTEND_API
    authentication_classes = (AuthenticationFromInternalHeaders,)
    permission_classes = (AccessTokensPermissions,)


class BaseUserApiViewSet(ReadOnlyModelViewSet, BaseUserApiView):
    pass


class ToolchainUserSerializer(ModelSerializer):
    MIN_USERNAME_LENGTH = 5

    class Meta:
        model = ToolchainUser
        fields = (
            "full_name",
            "email",
            "api_id",
            "username",
            "avatar_url",
        )
        read_only_fields = (
            "id",
            "api_id",
            "avatar_url",
            # deprecated fields, we don't use them
            "first_name",
            "last_name",
        )

    def run_validation(self, data=empty):
        if data:
            self._check_readonly_fields(data.keys())
        return super().run_validation(data=data)

    def _check_readonly_fields(self, field_names: Sequence[str]):
        # DRF just skips/ignores r/o fields in the request payload instead of rejecting the request w/ a validaton error (HTTP 400)
        # so we have this logic so we can reject requests that try to update r/o fields.
        errors = OrderedDict()
        for field_name in field_names:
            if field_name in self.Meta.read_only_fields:
                errors[field_name] = [ErrorDetail("Update not allowed.", code="read-only-field")]
        if errors:
            raise ValidationError(errors)

    def validate_email(self, value: str) -> str:
        allowed_emails = UserAuth.get_emails_for_user(self.instance.api_id)
        if value not in allowed_emails:
            raise ValidationError(ErrorDetail("Email not allowed.", code="invalid"))
        return value

    def validate_username(self, value: str) -> str:
        new_username = value.strip()
        if self.instance.username.lower() == new_username.lower():
            return new_username
        if len(new_username.strip()) < self.MIN_USERNAME_LENGTH:
            _logger.warning(f"username '{new_username}' too short")
            raise ValidationError(
                ErrorDetail(f"username must be at least {self.MIN_USERNAME_LENGTH} characters.", code="invalid")
            )
        return new_username


class SelfUserPermissions(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user.api_id == obj.api_id


class ToolchainUserViewSet(BaseUserApiViewSet, UpdateModelMixin):
    serializer_class = ToolchainUserSerializer
    queryset = ToolchainUser.active_users()
    lookup_field = "api_id"
    permission_classes = (AccessTokensPermissions, SelfUserPermissions)  # type: ignore[assignment]

    def permission_denied(self, request, message=None, code=None):
        if request.authenticators and not request.successful_authenticator:
            raise exceptions.NotAuthenticated()
        # We want to return 404 and not 403 in order not to indicate the existence of an object that the user is not allowed to access.
        raise exceptions.NotFound()

    @action(methods=["get"], detail=False, url_path="repos")
    def repos(self, request):
        user = request.user
        repos = Repo.for_user(user)
        serializer = RepoSerializer(repos, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(methods=["get"], detail=False, url_path="emails")
    def emails(self, request):
        user = request.user
        emails = UserAuth.get_emails_for_user(user.api_id)
        if not emails:
            _logger.warning(f"No email addresses associated with {user}")
        return Response({"emails": sorted(emails)})

    def update(self, request, api_id: str, partial: bool):
        return super().update(request, api_id=api_id, partial=partial)

    def list(self, request):
        return Response(status=HTTP_404_NOT_FOUND)

    def get_object(self):
        api_id = self.kwargs.get(self.lookup_field, USE_REQUEST_USER_ARG)
        if api_id == USE_REQUEST_USER_ARG:
            self.kwargs[self.lookup_field] = self.request.user.api_id
        return super().get_object()


class CustomerSerializer(ModelSerializer):
    scm = PrimaryKeyRelatedField(source="_scm_provider", read_only=True)

    class Meta:
        model = Customer
        fields = ("id", "name", "slug", "logo_url", "scm")

    def to_representation(self, instance: Customer):
        data = super().to_representation(instance)
        data["customer_link"] = get_customer_link(instance)
        if instance.is_limited:
            data["status"] = "limited"
        elif instance.is_in_free_trial:
            data["status"] = "free_trial"
        return data


class CustomerViewSet(BaseUserApiViewSet):
    serializer_class = CustomerSerializer
    pagination_class = ToolchainSlugCursorPagination

    def get_queryset(self):
        user = self.request.user
        user_api_id = _get_user_api_id(self.kwargs["user_api_id"], user)
        return Customer.for_api_id(user_api_id, user)


class RepoViewMetadata(BaseMetadata):
    def determine_metadata(self, request, view):
        user = request.user
        customer_slug = request.parser_context["kwargs"]["customer_pk"]
        customer = Customer.for_user_and_slug(user_api_id=user.api_id, slug=customer_slug)
        if not customer:
            _logger.warning(f"customer not found. {customer_slug=} {user=}")
            raise Http404
        return _get_customer_metadata(customer)


class RepoSerializer(ModelSerializer):
    customer_slug = PrimaryKeyRelatedField(source="customer.slug", read_only=True)
    customer_logo = PrimaryKeyRelatedField(source="customer.logo_url", read_only=True)
    scm = PrimaryKeyRelatedField(source="customer._scm_provider", read_only=True)

    class Meta:
        model = Repo
        fields = ("id", "name", "customer_id", "slug", "customer_slug", "customer_logo", "scm")

    def to_representation(self, instance: Repo):
        data = super().to_representation(instance)
        customer_link = get_customer_link(instance.customer)
        data.update(repo_link=f"{customer_link}{instance.slug}/", customer_link=customer_link)
        return data


class RepoViewSet(BaseUserApiViewSet):
    serializer_class = RepoSerializer
    pagination_class = ToolchainSlugCursorPagination
    metadata_class = RepoViewMetadata

    def get_queryset(self):
        user = self.request.user
        user_api_id = _get_user_api_id(self.kwargs["user_api_id"], user)
        customer_slug = self.kwargs["customer_pk"]
        customer = Customer.for_user_and_slug(user_api_id=user_api_id, slug=customer_slug)
        return Repo.for_customer(customer)


def _get_user_api_id(user_api_id: str, user: ToolchainUser) -> str:
    api_id = user.api_id if user_api_id == USE_REQUEST_USER_ARG else user_api_id
    if api_id != user.api_id:
        _logger.warning(f"user={user} tried to load data for a different user: {user_api_id}")

        raise Http404()
    return api_id


_HOSTS = {
    Customer.Scm.BITBUCKET: "bitbucket.org",
    Customer.Scm.GITHUB: "github.com",
}


def get_customer_link(customer: Customer):
    host = _HOSTS[customer.scm_provider]
    return f"https://{host}/{customer.slug}/"


class EditTokenForm(ToolchainForm):
    description = CharField(required=True, min_length=2, max_length=250)

    def clean_description(self) -> str:
        return self.cleaned_data["description"].strip()


class AllocatedTokensView(BaseUserApiViewSet):
    def list(self, request):
        user = request.user
        tokens = AllocatedRefreshToken.get_api_tokens_for_user(user.api_id)
        tokens_json = [_serialize_token(token) for token in tokens]
        max_reached = AllocatedRefreshToken.has_reached_max_api_tokens(user.api_id)
        return Response(
            data={
                "tokens": tokens_json,
                "max_reached": max_reached,
                "max_tokens": AllocatedRefreshToken.get_max_api_tokens(),
            }
        )

    def destroy(self, request, pk: str):
        token = AllocatedRefreshToken.get_for_user_or_404(token_id=pk, user_api_id=request.user.api_id)
        if not token.is_active:
            _logger.warning(f"Can't revoke inactive token: token_id={token.id} state={token.state.value}")
            return Response(data={"token": ["Token is not active."]}, status=HttpResponseBadRequest.status_code)
        token.revoke()
        return Response(status=201, data={"result": "ok"})

    def partial_update(self, request, pk: str):  # HTTP patch
        form = EditTokenForm(request.data)
        if not form.is_valid():
            _logger.warning(f"Bad input in form: data={request.data} {form.errors=}")
            return Response({"errors": form.errors.get_json_data()}, status=HttpResponseBadRequest.status_code)
        description = form.cleaned_data["description"]
        token = AllocatedRefreshToken.get_for_user_or_404(token_id=pk, user_api_id=request.user.api_id)
        token.set_description(desc=description)
        return Response(status=201, data={"description": description})


def _serialize_token(token) -> dict:
    audiences = token.audiences
    token_json = {
        "id": token.id,
        "issued_at": token.issued_at.isoformat(),
        "expires_at": token.expires_at.isoformat(),
        "last_seen": token.last_seen.isoformat() if token.last_seen else None,
        "description": token.description or None,
        "state": token.state.value.capitalize(),
        "can_revoke": token.is_active,
        "permissions": audiences.to_claim() if audiences else [],
    }
    # For now this is optional, because existing tokens don't have those fields.
    if token.repo_id:
        token_json.update(
            {
                "repo": {"id": token.repo_id, "name": token.repo_name, "slug": token.repo_slug},
                "customer": {"id": token.customer_id, "name": token.customer_name, "slug": token.customer_slug},
            }
        )
    return token_json


class UserCustomerPermissions(BasePermission):
    _WRITE_HTTP_METHODS = frozenset(["POST", "PATCH", "PUT", "DELETE"])

    def has_permission(self, request, view) -> bool:
        is_write = request.method.upper() in self._WRITE_HTTP_METHODS
        if not is_write:
            return True
        return view.role.is_admin


class CustomerAdminOnlyPermissions(BasePermission):
    def has_permission(self, request, view) -> bool:
        if not view.role.is_admin:
            _logger.warning(f"User {request.user} is not org admin. role: {view.role.value}")
        return view.role.is_admin


class EditCustomerForm(ToolchainForm):
    name = CharField(
        required=True,
        min_length=2,
        max_length=128,
        validators=[
            RegexValidator(
                r"^[a-zA-Z0-9,\.\- ]*$", "Only English letters, numbers, dot, comma, spaces and dashes are allowed."
            )
        ],
    )

    def clean_name(self) -> str:
        return self.cleaned_data["name"].strip()


class BaseCustomerView(BaseUserApiView):
    permission_classes = (AccessTokensPermissions, UserCustomerPermissions)  # type: ignore[assignment]

    def initial(self, request, *args, **kwargs):
        slug = kwargs["customer_slug"]
        user = request.user
        if not user.is_authenticated:
            _logger.warning(f"User not authenticated: {user} {request.method=} {request.path=}")
            raise exceptions.NotAuthenticated()
        self.customer = Customer.for_user_and_slug(user_api_id=user.api_id, slug=slug)
        if not self.customer:
            _logger.warning(f"no customer={slug} for {user}")
            raise Http404
        self.role = UserCustomerAccessConfig.get_role_for_user(customer_id=self.customer.id, user_api_id=user.api_id)
        super().initial(request, *args, **kwargs)


class CustomerView(BaseCustomerView):
    def get(self, request, customer_slug):
        customer_link = get_customer_link(self.customer)
        scm = self.customer.scm_provider.value
        customer_data = {
            "id": self.customer.id,
            "slug": self.customer.slug,
            "name": self.customer.name,
            "logo_url": self.customer.logo_url,
            "scm": scm,
            "customer_link": customer_link,
        }
        if self.role.is_admin:
            customer_data["billing"] = reverse(URLNames.CUSTOMER_BILLING, kwargs={"customer_slug": customer_slug})
        repo_qs = Repo.for_customer_id(self.customer.id, include_inactive=self.role.is_admin)
        return Response(
            data={
                "customer": customer_data,
                "repos": [_serialize_repo(repo=repo, customer_link=customer_link, scm=scm) for repo in repo_qs],
                "metadata": _get_customer_metadata(self.customer),
                "user": {
                    "role": self.role.value,
                    "is_admin": self.role.is_admin,
                },
            }
        )

    def patch(self, request, customer_slug: str):
        form = EditCustomerForm(request.data)
        if not form.is_valid():
            _logger.warning(f"Bad input in form: data={request.data} {form.errors=}")
            return Response({"errors": form.errors.get_json_data()}, status=HttpResponseBadRequest.status_code)
        self.customer.set_name(form.cleaned_data["name"])
        return Response(status=201, data={"ok": "ok"})


class CustomerPlanView(BaseCustomerView):
    _PLANS_MAP = {
        "Starter Plan": {
            "description": "For small teams getting started with Pants",
            "resources": [
                "Teams of up to 10 developers",
                "Up to 100 GB cache storage",
                "Up to 500 GB outbound data transfer per month",
                "Community support",
                "Free to try for 30 days",
            ],
        },
        "Enterprise Plan": {
            "description": "For growing teams of all sizes",
            "resources": [
                "Teams of any size",
                "Cache storage as needed",
                "Data transfer as needed",
                "Enterprise support",
            ],
        },
    }

    def get(self, request, customer_slug):
        client = PaymentsCustomerClient.for_customer(settings, customer_id=self.customer.id)
        plan_and_usage = client.get_plan_and_usage()
        if plan_and_usage.plan:
            plan_json = {"name": plan_and_usage.plan, "price": plan_and_usage.price}
            if plan_and_usage.trial_end:
                plan_json.update(
                    trial_end=plan_and_usage.trial_end.isoformat(),
                    has_trail_ended=plan_and_usage.trial_end < utcnow().date(),
                )

            plan_key = plan_and_usage.plan if plan_and_usage.plan in self._PLANS_MAP else "Starter Plan"
            plan_json.update(self._PLANS_MAP[plan_key])
        else:
            plan_json = None
        responses_data = {
            "plan": plan_json,
            "usage": {
                "bandwidth": {
                    "outbound": naturalsize(plan_and_usage.cache_read_bytes)
                    if plan_and_usage.cache_read_bytes
                    else None,
                    "inbound": naturalsize(plan_and_usage.cache_write_bytes)
                    if plan_and_usage.cache_write_bytes
                    else None,
                }
            },
        }
        return Response(data=responses_data)


class CustomerRepoView(BaseCustomerView):
    permission_classes = (AccessTokensPermissions, CustomerAdminOnlyPermissions)  # type: ignore[assignment]

    def post(self, request, customer_slug: str, repo_slug: str):
        repo = Repo.get_by_slug_and_customer_id(customer_id=self.customer.id, slug=repo_slug, include_inactive=True)
        if not repo:
            _logger.warning(f"Can't find repo {repo_slug=} for customer={self.customer}")
            raise Http404

        if repo.is_active:
            _logger.warning(f"repo {repo} already active.")
            return self._repo_response(200, repo)
        if not Repo.allow_repo_activation(self.customer.id):
            _logger.warning(f"Max active repos for {self.customer} reached.")
            return Response(
                data={"detail": "Max active repos customer reached."}, status=HttpResponseBadRequest.status_code
            )
        repo.activate()
        return self._repo_response(201, repo)

    def delete(self, request, customer_slug: str, repo_slug: str):
        repo = Repo.get_by_slug_and_customer_id(customer_id=self.customer.id, slug=repo_slug, include_inactive=True)
        if not repo:
            _logger.warning(f"Can't find repo {repo_slug=} for customer={self.customer}")
            raise Http404

        if not repo.is_active:
            _logger.warning(f"repo {repo} not active.")
            return self._repo_response(200, repo)
        repo.deactivate()
        return self._repo_response(201, repo)

    def _repo_response(self, status_code, repo: Repo):
        customer_link = get_customer_link(self.customer)
        return Response(
            status=status_code,
            data={
                "repo": _serialize_repo(repo=repo, customer_link=customer_link, scm=self.customer.scm_provider.value)
            },
        )


class CustomerBillingView(BaseCustomerView):
    permission_classes = (AccessTokensPermissions, CustomerAdminOnlyPermissions)  # type: ignore[assignment]

    def post(self, request, customer_slug: str):
        client = StripeCustomerClient.for_customer(settings, customer_id=self.customer.id)
        return_url = request.headers.get("referer")
        # Make sure referer wasn't manipulated.
        parsed_url = urlparse(return_url)
        if parsed_url.netloc != request.get_host() or parsed_url.scheme != request.scheme:
            _logger.warning(f"Invalid value for `referer` header: {return_url=}")
            raise ParseError(detail="Invalid value for `referer` header")
        session_url = client.create_portal_session(return_url=return_url)
        if not session_url:
            _logger.warning(f"Can't create portal session for customer: {self.customer}")
            raise NotFound(detail="Access to plan management UI is not available yet. Try again in a few minutes.")
        return Response(status=201, data={"session_url": session_url})


def _get_customer_metadata(customer: Customer) -> dict[str, str]:
    if customer.scm_provider != Customer.Scm.GITHUB:
        # TODO: Add Support bitbucket customers
        return {}
    client = GithubCustomerReposClient.for_customer(django_settings=settings, customer_id=customer.id)
    info = client.get_install_info()
    metadata = {"install_link": info.install_link}
    if info.configure_link:
        metadata["configure_link"] = info.configure_link
    return metadata


def _serialize_repo(repo: Repo, customer_link: str, scm: str) -> dict[str, str | bool]:
    return {
        "id": repo.id,
        "name": repo.name,
        "slug": repo.slug,
        "is_active": repo.is_active,
        "repo_link": f"{customer_link}{repo.slug}",
        "scm": scm,
    }


def _can_access_remote_worker_tokens(customer: Customer, role: UserCustomerAccessConfig) -> bool:
    if customer.slug not in settings.ALLOWED_REMOTE_EXEC_CUSTOMERS_SLUGS:
        _logger.warning(f"Customer: {customer.slug} not allowed to use remote worker tokens.")
        return False
    if customer.is_open_source and not role.is_admin:
        _logger.warning(f"Customer: {customer.slug} is OSS, only org admin can access remote worker tokens.")
        return False
    return True


class RemoteWorkerTokensPermissions(BasePermission):
    def has_permission(self, request, view) -> bool:
        if request.method.upper() == "OPTIONS":
            # this method is used to check if the UI should be shown and if other APIs are accessible.
            return True
        return _can_access_remote_worker_tokens(customer=view.customer, role=view.role)


class BaseCustomerRemoteWorkerTokensViews(BaseCustomerView):
    #  All users associated with customer can perform any operation with remote worker tokens.
    permission_classes = (AccessTokensPermissions, RemoteWorkerTokensPermissions)  # type: ignore[assignment]


class CustomerRemoteWorkerTokensView(BaseCustomerRemoteWorkerTokensViews):
    def options(self, request, customer_slug: str):
        return Response(data={"allowed": _can_access_remote_worker_tokens(customer=self.customer, role=self.role)})

    def get(self, request, customer_slug: str):
        tokens = RemoteExecWorkerToken.get_for_customer(customer_id=self.customer.id)
        return Response(data={"tokens": [_serialize_remote_worker_token(token) for token in tokens]})

    def post(self, request, customer_slug: str):
        # TODO: check limit (per customer)
        user = request.user
        description = request.data.get("description", f"Created by {user.username}")[:256]
        _logger.info(f"Create remote worker token for {customer_slug=} {description=}")
        token = RemoteExecWorkerToken.create(
            customer_id=self.customer.id,
            customer_slug=self.customer.slug,
            user_api_id=user.api_id,
            description=description,
        )
        return Response(data={"token": _serialize_remote_worker_token(token)})


class CustomerRemoteWorkerTokenView(BaseCustomerRemoteWorkerTokensViews):
    def delete(self, request, customer_slug: str, token_id: str):
        _logger.info(f"delete remote worker token for {customer_slug=} {token_id=}")
        token = RemoteExecWorkerToken.deactivate_or_404(customer_id=self.customer.id, token_id=token_id)
        return Response(data={"token": _serialize_remote_worker_token(token)})


def _serialize_remote_worker_token(rw_token: RemoteExecWorkerToken) -> dict[str, str]:
    token_dict = {
        "id": rw_token.id,
        "created_at": rw_token.created_at.isoformat(),
        "state": rw_token.state.value,
        "description": rw_token.description,
        "token": rw_token.token,
    }
    if not rw_token.is_active:
        del token_dict["token"]
    return token_dict
