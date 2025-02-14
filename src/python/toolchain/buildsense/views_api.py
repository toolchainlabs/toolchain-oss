# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import logging

from django.forms import BooleanField, CharField, ChoiceField, DateTimeField, IntegerField, ValidationError
from django.http import Http404, HttpResponseBadRequest
from django.urls import reverse
from more_itertools import locate, seekable
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from toolchain.base.datetime_tools import utcnow
from toolchain.buildsense.build_data_queries import BuildsQueries, FieldsMap
from toolchain.buildsense.ingestion.metrics_store import MissingBucketError, PantsMetricsStore
from toolchain.buildsense.records.run_info import CIDetails, RunInfo
from toolchain.django.forms.base_form import ToolchainForm
from toolchain.django.site.models import CustomerScmProvider, Repo, ToolchainUser
from toolchain.users.jwt.authentication import AuthenticationFromInternalHeaders
from toolchain.users.jwt.permissions import AccessTokensPermissions
from toolchain.users.jwt.utils import AccessTokenAudience

_logger = logging.getLogger(__name__)


class BuildDateTimeField(DateTimeField):
    _DATETIME_INPUT_FORMAT = "%Y-%m-%d %H:%M:%S"  # '2018-10-25 14:30:59'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, required=False, input_formats=[self._DATETIME_INPUT_FORMAT], **kwargs)


class BuildsQueryForm(ToolchainForm):
    page_size = IntegerField(required=False, min_value=1, max_value=40)
    cursor = CharField(required=False)
    # We expect UTC values from here.
    earliest = BuildDateTimeField()
    latest = BuildDateTimeField()

    def clean(self):
        cleaned = super().clean()
        earliest = cleaned.get("earliest")
        latest = cleaned.get("latest")
        if latest and earliest and latest < earliest:
            raise ValidationError("Invalid date range.", code="range")


class BuildSearchForm(ToolchainForm):
    MAX_PAGES = 30
    # We expect UTC values from here.
    earliest = BuildDateTimeField()
    latest = BuildDateTimeField()
    cmd_line = CharField(required=False)
    outcome = CharField(required=False)
    branch = CharField(required=False)
    goals = CharField(required=False)
    ci = BooleanField(required=False)
    pr = IntegerField(required=False)
    user_api_id = CharField(required=False)
    user = CharField(required=False)
    title = CharField(required=False)
    run_time_min = IntegerField(required=False, min_value=0, max_value=datetime.timedelta(days=3).total_seconds())
    run_time_max = IntegerField(required=False, min_value=0, max_value=datetime.timedelta(days=3).total_seconds())
    page_size = IntegerField(required=False, min_value=1, max_value=50)
    page = IntegerField(required=False, min_value=1, max_value=MAX_PAGES)
    sort = ChoiceField(
        required=False,
        choices=(
            ("timestamp", "Timestamp ASC"),
            ("-timestamp", "Timestamp DESC"),
            ("run_time", "Run time ASC"),
            ("-run_time", "Run time DESC"),
            ("outcome", "Outcome ASC"),
            ("-outcome", "Outcome ASC"),
        ),
    )
    _FIELD_MAP_FIELDS = {"cmd_line", "outcome", "branch", "user_api_id", "goals", "run_time", "pr", "title"}

    def clean(self):
        cleaned = super().clean()
        earliest = cleaned.get("earliest")
        latest = cleaned.get("latest")
        user = cleaned["user"]
        user_api_id = cleaned["user_api_id"]
        if user and user_api_id:
            raise ValidationError("Specifying both user & user_api_id is not supported.", code="invalid")
        if latest and earliest and latest < earliest:
            raise ValidationError("Invalid date range.", code="range")
        rt_min = cleaned.get("run_time_min")
        rt_max = cleaned.get("run_time_max")
        if rt_min and rt_max and rt_max < rt_min:
            raise ValidationError("Invalid run time range.", code="range")
        if rt_min or rt_max:
            cleaned["run_time"] = (rt_min, rt_max)
        else:
            cleaned["run_time"] = None

    def clean_run_time_min(self) -> datetime.timedelta | None:
        seconds = self.cleaned_data["run_time_min"]
        return datetime.timedelta(seconds=seconds) if seconds else None

    def clean_run_time_max(self) -> datetime.timedelta | None:
        seconds = self.cleaned_data["run_time_max"]
        return datetime.timedelta(seconds=seconds) if seconds else None

    def clean_goals(self) -> list[str]:
        goals = self.cleaned_data["goals"].strip()
        return [goal.strip() for goal in goals.split(",")] if goals else []

    def get_fields_map(self, user_api_id: str | None = None) -> FieldsMap:
        data = self.cleaned_data
        fields_map = {field: data[field] for field in self._FIELD_MAP_FIELDS if data.get(field)}
        if "ci" in self.data:
            fields_map["ci"] = data["ci"]
        if user_api_id:
            fields_map["user_api_id"] = user_api_id
        return fields_map


class BaseBuildsenseView(APIView):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        repo_slug = kwargs["repo_slug"]
        customer_slug = kwargs["customer_slug"]
        # Ensures the user has access to the Repo/Customer.
        self.repo = Repo.get_or_404_for_slugs_and_user(
            repo_slug=repo_slug, customer_slug=customer_slug, user=request.user
        )


class BuildViewSet(ViewSet, BaseBuildsenseView):
    lookup_field = "run_id"
    view_type = "app"
    audience = AccessTokenAudience.FRONTEND_API
    authentication_classes = (AuthenticationFromInternalHeaders,)
    permission_classes = (AccessTokensPermissions,)
    MIN_SUGGEST_QUERY_SIZE = 3
    _REPO_ONBOARDING_LINK = (
        "https://docs.toolchain.com/docs/getting-started-with-toolchain#configure-pants-to-use-toolchain"
    )

    def _get_fields_map(self, form: BuildSearchForm, user: ToolchainUser) -> FieldsMap:
        user_query = form.cleaned_data["user"]
        if user_query:
            if user_query.lower() == "me":
                user_api_id = user.api_id
            else:
                user_api_id = ToolchainUser.get_user_api_id_for_username(
                    username=user_query, customer_id=self.repo.customer_id
                )
                if not user_api_id:
                    # user_query is not a username so assume it is a user_api_id
                    user_api_id = user_query
        else:
            user_api_id = None
        return form.get_fields_map(user_api_id=user_api_id)

    def list(self, request, repo_slug: str, customer_slug: str | None = None):
        user = request.user
        form = BuildSearchForm(request.query_params)
        if not form.is_valid():
            _logger.warning(f"Bad input in form: {form.errors}")
            return Response({"errors": form.errors.get_json_data()}, status=HttpResponseBadRequest.status_code)
        field_map = self._get_fields_map(form, user)
        page = form.cleaned_data["page"] or 0
        queries = BuildsQueries.for_customer_id(self.repo.customer_id)
        search_result = queries.search_all_matching(
            repo_id=self.repo.pk,
            field_map=field_map,
            earliest=form.cleaned_data["earliest"],
            latest=form.cleaned_data["latest"],
            page_size=form.cleaned_data["page_size"],
            sort=form.cleaned_data["sort"],
            page=page,
        )

        builds_json = _serialize_builds(
            repo=self.repo,
            remove_internal_details=True,
            builds=search_result.results,
        )
        response_json = {
            "results": builds_json,
            "count": search_result.count,
            "max_pages": min(search_result.total_pages, BuildSearchForm.MAX_PAGES),
            "total_pages": search_result.total_pages,
        }
        if search_result.offset:
            response_json["offset"] = search_result.offset
        if page > 1:
            response_json["page"] = page
        return Response(data=response_json)

    @action(methods=["get"], detail=False, url_path="indicators")
    def indicators(self, request, repo_slug: str, customer_slug: str | None = None):
        metrics_store = PantsMetricsStore.for_repo(self.repo)
        form = BuildSearchForm(request.query_params)
        if not form.is_valid():
            _logger.warning(f"Bad input in form: {form.errors}")
            return Response({"errors": form.errors.get_json_data()}, status=HttpResponseBadRequest.status_code)
        fields_map = self._get_fields_map(form, user=request.user)
        try:
            indicators = metrics_store.get_aggregated_indicators(
                earliest=form.cleaned_data["earliest"] or utcnow() - datetime.timedelta(days=31),
                latest=form.cleaned_data["latest"],
                fields_map=fields_map,
            )
        except MissingBucketError as error:
            _logger.warning(f"Missing metrics buckets for repo: {self.repo} {error!r}")
            raise Http404
        response_json = {"indicators": indicators}
        return Response(data=response_json)

    def options(self, request, repo_slug: str, customer_slug: str | None = None):
        user = request.user
        queries = BuildsQueries.for_customer_id(self.repo.customer_id)
        field_names = request.query_params.get("field")
        if not field_names:
            _logger.warning(f"Missing field param: {request.query_params}")
            return Response(
                {"errors": [{"code": "missing", "message": "Missing 'field'"}]},
                status=HttpResponseBadRequest.status_code,
            )
        if len(request.query_params) != 1:
            _logger.warning(f"Unused parameters: {request.query_params}")
            return Response(
                {"errors": [{"code": "invalid", "message": "Unused query parameters"}]},
                status=HttpResponseBadRequest.status_code,
            )
        fields = field_names.split(",")
        fields_set = set(fields)
        if len(fields_set) != len(fields):
            _logger.warning(f"Same field specified multiple times: {fields}")
            return Response(
                {"errors": [{"code": "invalid", "message": "Invalid field value"}]},
                status=HttpResponseBadRequest.status_code,
            )
        if not fields_set.issubset(queries.allowed_get_values_fields):
            _logger.warning(f"Invalid field names detected: {fields}")
            return Response(
                {"errors": [{"code": "invalid", "message": "Invalid field value"}]},
                status=HttpResponseBadRequest.status_code,
            )
        if not queries.repo_has_builds(repo_id=self.repo.pk):
            return Response({"status": "no_builds", "docs": self._REPO_ONBOARDING_LINK})
        values_map = queries.get_values(repo_id=self.repo.pk, field_names=tuple(fields))
        if "user_api_id" in values_map:
            api_ids = values_map["user_api_id"]["values"]
            if api_ids:
                values_map["user_api_id"]["values"] = self._get_users_values(user, api_ids)
        summary = " ".join(f"({name}={len(values)})" for name, values in values_map.items())
        _logger.info(f"get_values: {summary}")
        return Response(values_map)

    def _get_users_values(self, current_user: ToolchainUser, user_api_ids):
        users = seekable(ToolchainUser.with_api_ids(user_api_ids=user_api_ids, include_inactive=True))
        # Make sure current user is first on the list.
        idx = next(locate(users, pred=lambda user: user.id == current_user.id), None)
        users.seek(0)
        users_dicts = [_serialize_user(user) for user in users]
        if idx:
            users_dicts.insert(0, users_dicts.pop(idx))
        _logger.info(f"field_name=user_api_id values_count={len(user_api_ids)} users={len(users_dicts)} current={idx}")
        return users_dicts

    def _is_raw_data_access_allowed(self, request) -> bool:
        # Toolchain admins only for now (due to PII and leak implementation details)
        return bool(request.toolchain_impersonation or request.user.is_staff)

    def retrieve(self, request, repo_slug: str, run_id: str, customer_slug: str | None = None):
        user = request.user
        repo = self.repo
        user_api_id = _get_user_api_id(request)
        queries = BuildsQueries.for_customer_id(self.repo.customer_id)
        run_info = queries.get_build(repo_id=repo.pk, user_api_id=user_api_id, run_id=run_id)
        if not run_info:
            _logger.warning(f"No {run_id=} for {repo=} user_api_id={user_api_id}")
            raise Http404
        if user.api_id != run_info.user_api_id:
            build_user = next(ToolchainUser.with_api_ids((run_info.user_api_id,), include_inactive=True))
        else:
            build_user = user
        expired_builds_threshold = _get_expired_builds_threshold()
        run_info_json = _serialize_build(
            repo=repo,
            build=run_info,
            user_data=_serialize_user(build_user),
            expired_builds_threshold=expired_builds_threshold,
            remove_internal_details=True,
        )

        include_raw_data_link = self._is_raw_data_access_allowed(request)
        download_links = _get_build_download_links(
            repo=repo, build=run_info, include_raw_data_link=include_raw_data_link
        )
        run_info_json.update(
            build_artifacts=queries.get_build_artifacts(repo, run_info),
            download_links=download_links,
        )
        if run_info.collected_platform_info:
            platform_info = queries.get_platform_info(repo, run_info)
            if platform_info:
                run_info_json["platform"] = platform_info
        return Response({"run_info": run_info_json})

    def _get_raw_data(self, run_id: str, user_api_id: str) -> dict:
        queries = BuildsQueries.for_customer_id(self.repo.customer_id)
        raw_data = queries.get_build_raw_data(repo=self.repo, user_api_id=user_api_id, run_id=run_id)
        if not raw_data:
            _logger.warning(f"No raw data available for run_id={run_id}")
            raise Http404
        return raw_data

    @action(methods=["get"], detail=True, url_path="raw")
    def get_raw_data(self, request, repo_slug: str, run_id: str, customer_slug: str | None = None):
        user = request.user
        if not self._is_raw_data_access_allowed(request):
            _logger.warning(f"get_raw_data denied for {user}")
            raise PermissionDenied("not allowed")
        raw_data = self._get_raw_data(run_id=run_id, user_api_id=_get_user_api_id(request))
        return Response(raw_data)

    @action(methods=["get"], detail=True, url_path="workunits")
    def get_workunits_data(self, request, repo_slug: str, run_id: str, customer_slug: str | None = None):
        raw_data = self._get_raw_data(run_id=run_id, user_api_id=_get_user_api_id(request))
        if "workunits" not in raw_data:
            _logger.warning(f"missing work units data from {run_id=} {raw_data.keys()=}")
            raise NotFound("No Work Units associated with this build.")
        return Response(raw_data["workunits"])

    @action(methods=["get"], detail=True, url_path="trace")
    def get_trace_data(self, request, repo_slug: str, run_id: str, customer_slug: str | None = None):
        user_api_id = _get_user_api_id(request)
        queries = BuildsQueries.for_customer_id(self.repo.customer_id)
        trace_json = queries.get_build_trace(repo=self.repo, user_api_id=user_api_id, run_id=run_id)
        if not trace_json:
            _logger.warning(f"No trace available for {run_id=}")
            raise Http404
        return Response(trace_json)

    @action(methods=["get"], detail=False, url_path="suggest")
    def suggest_values(self, request, repo_slug: str, customer_slug: str | None = None):
        queries = BuildsQueries.for_customer_id(self.repo.customer_id)
        # For now, we only suggest on RunInfo.title, but if we want to suggest on more fields,
        # we should add a query param to specify the field to suggest values for.
        query = request.query_params.get("q")
        if not query:
            _logger.warning(f"Missing query (q) param: {request.query_params}")
            return Response(
                {"errors": [{"code": "missing", "message": "Missing 'q'"}]},
                status=HttpResponseBadRequest.status_code,
            )
        if len(request.query_params) != 1:
            _logger.warning(f"Unused parameters: {request.query_params}")
            return Response(
                {"errors": [{"code": "invalid", "message": "Unused query parameters"}]},
                status=HttpResponseBadRequest.status_code,
            )
        if len(query) < self.MIN_SUGGEST_QUERY_SIZE:  # minimal 3 characters do do a query
            _logger.warning(f"Invalid query value: {query=}")
            return Response(
                {
                    "errors": [
                        {
                            "code": "invalid",
                            "message": f"Invalid query value, must be at least {self.MIN_SUGGEST_QUERY_SIZE} characters",
                        }
                    ]
                },
                status=HttpResponseBadRequest.status_code,
            )

        values = queries.suggest_title_values(repo_id=self.repo.pk, query=query)
        return Response({"values": values})


class BuildArtifactsView(BaseBuildsenseView):
    view_type = "app"
    audience = AccessTokenAudience.FRONTEND_API
    authentication_classes = (AuthenticationFromInternalHeaders,)
    permission_classes = (AccessTokensPermissions,)

    def get(self, request, repo_slug: str, run_id: str, artifact_id: str, customer_slug: str | None = None):
        user_api_id = _get_user_api_id(request)
        queries = BuildsQueries.for_customer_id(self.repo.customer_id)
        artifact_file = queries.get_build_artifact(self.repo, user_api_id, run_id, name=artifact_id)
        if not artifact_file:
            raise Http404
        return Response(data=json.loads(artifact_file.content), content_type="application/json")


def _get_user_api_id(request) -> str:
    user = request.user
    user_api_id = request.query_params.get("user_api_id")
    if user_api_id == "me":
        user_api_id = user.api_id
    return user_api_id


def _get_expired_builds_threshold() -> datetime.datetime:
    return utcnow() - datetime.timedelta(minutes=5)


def _serialize_build(
    repo: Repo,
    build: RunInfo,
    user_data: dict[str, str | None],
    expired_builds_threshold: datetime.datetime,
    remove_internal_details: bool,
):
    build_json = build.to_json_dict()
    # TODO: UI might want an object here not a string, at any case, we should not send the entire model since
    # it might contain data we don't want to leak out.
    link = reverse(
        "builds-detail", kwargs={"customer_slug": repo.customer.slug, "repo_slug": repo.slug, "run_id": build.run_id}
    )
    del build_json["timestamp"]  # Remove the timestamp as the UI uses `datetime`.
    del build_json["user_api_id"]
    del build_json["computed_goals"]
    del build_json["modified_fields"]
    del build_json["collected_platform_info"]
    if not build_json["indicators"]:
        del build_json["indicators"]
    build_json["outcome"] = _get_outcome(build, expired_builds_threshold)
    if build.ci_info:
        build_json["ci_info"]["links"] = _get_ci_links(repo.customer.scm_provider, build, build.ci_info)
        del build_json["ci_info"]["link"]
        del build_json["ci_info"]["build_url"]
        del build_json["ci_info"]["ref_name"]
    build_json.update(
        {
            "user": user_data,
            "repo_slug": repo.slug,
            "datetime": build.timestamp.isoformat(),
            "link": link,
            "is_ci": bool(build.ci_info),
            "goals": _get_goals(build),
        }
    )
    if remove_internal_details:
        del build_json["server_info"]
    else:
        build_json["server_info"]["accept_time"] = build.server_info.accept_time.isoformat()
    return build_json


def _get_build_download_links(repo: Repo, build: RunInfo, include_raw_data_link: bool) -> list[dict[str, str]]:
    build_data_links = [
        {
            "name": "workunits",
            "link": reverse(
                "builds-get-workunits-data",
                kwargs={"customer_slug": repo.customer.slug, "repo_slug": repo.slug, "run_id": build.run_id},
            ),
        }
    ]
    if build.has_trace:
        build_data_links.append(
            {
                "name": "trace",
                "link": reverse(
                    "builds-get-trace-data",
                    kwargs={"customer_slug": repo.customer.slug, "repo_slug": repo.slug, "run_id": build.run_id},
                ),
            }
        )
    if include_raw_data_link:
        build_data_links.append(
            {
                "name": "raw",
                "link": reverse(
                    "builds-get-raw-data",
                    kwargs={"customer_slug": repo.customer.slug, "repo_slug": repo.slug, "run_id": build.run_id},
                ),
            }
        )
    return build_data_links


def _get_outcome(build: RunInfo, expired_builds_threshold: datetime.datetime) -> str:
    if build.outcome != "NOT_AVAILABLE":
        return build.outcome
    if build.server_info.accept_time > expired_builds_threshold:
        return "RUNNING"
    return "TIMEOUT"


def _get_ci_links(scm: CustomerScmProvider, run_info: RunInfo, ci_info: CIDetails) -> list[dict[str, str]]:
    links = []
    if ci_info.link:
        if ci_info.run_type == CIDetails.Type.BRANCH:
            text = f"Branch {run_info.branch}"
        elif ci_info.run_type == CIDetails.Type.PULL_REQUEST:
            text = f"Pull request {ci_info.pull_request}"
        elif ci_info.run_type == CIDetails.Type.TAG:
            # TODO: we need to support tagging as a build trigger
            text = "Tag/Release"
        else:
            text = "Unknown run type"
        links.append({"icon": scm.value, "text": text, "link": ci_info.link})
    ci_system = ci_info.ci_system
    if ci_system.is_known and ci_info.build_url:
        links.append({"icon": ci_system.value, "text": ci_info.job_name or "Unknown", "link": ci_info.build_url})
    return links


def _get_goals(build: RunInfo) -> list[str]:
    targets = build.specs_from_command_line
    goals = build.computed_goals
    if len(targets) == len(goals) == 1 and goals[0] == "run":
        *_, target = targets[0].partition(":")
        goals = [f"run {target}"]
    return goals


def _serialize_user(user: ToolchainUser) -> dict[str, str | None]:
    full_name = user.get_full_name() or None
    return {
        "username": user.username,
        "api_id": user.api_id,
        "full_name": full_name,
        "avatar_url": user.avatar_url or None,
    }


def _serialize_builds(repo: Repo, remove_internal_details: bool, builds: tuple[RunInfo, ...]):
    if not builds:
        return []
    expired_builds_threshold = _get_expired_builds_threshold()
    user_api_ids = {build.user_api_id for build in builds}
    users_map = (
        {user.api_id: _serialize_user(user) for user in ToolchainUser.with_api_ids(user_api_ids, include_inactive=True)}
        if bool(user_api_ids)
        else {}
    )
    return [
        _serialize_build(
            repo=repo,
            build=build,
            user_data=users_map[build.user_api_id],
            expired_builds_threshold=expired_builds_threshold,
            remove_internal_details=remove_internal_details,
        )
        for build in builds
        if users_map.get(build.user_api_id, False)
    ]
