# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import logging
import re
from io import BytesIO

from django import http
from django.http.request import HttpHeaders
from rest_framework.exceptions import ParseError, PermissionDenied
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from toolchain.base.datetime_tools import utcnow
from toolchain.buildsense.ingestion.errors import BadDataError
from toolchain.buildsense.ingestion.pants_data_ingestion import PantsDataIngestion, RequestContext
from toolchain.buildsense.ingestion.utils import DecompressFailed, decompress
from toolchain.django.auth.claims import RepoClaims
from toolchain.django.auth.constants import AccessTokenAudience
from toolchain.django.site.models import Repo, ToolchainUser
from toolchain.django.site.utils.request_utils import get_client_ip
from toolchain.users.jwt.authentication import AuthenticationFromInternalHeaders
from toolchain.users.jwt.permissions import AccessTokensPermissions

_logger = logging.getLogger(__name__)


def _get_impersonation_user(claims: RepoClaims) -> ToolchainUser | None:
    impersonated_user_api_id = claims.impersonated_user_api_id
    if not impersonated_user_api_id:
        return None
    ci_user = ToolchainUser.get_by_api_id(impersonated_user_api_id)
    if not ci_user:
        _logger.warning(f"Can't impersonate user: {impersonated_user_api_id}")
    return ci_user


def _decompress(context: str, data: bytes) -> bytes:
    try:
        return decompress(context, data)
    except DecompressFailed as error:
        raise ParseError(str(error))


def _is_compressed(headers: HttpHeaders) -> bool:
    encoding = headers.get("Content-Encoding")
    return encoding and encoding in ("gzip", "compress")


class CompressedJsonParser(JSONParser):
    def parse(self, stream, media_type=None, parser_context=None):
        request = parser_context["request"]
        is_compressed = _is_compressed(request.headers)
        _logger.warning(f"using CompressedJsonParser: {is_compressed=} {request.path=}")
        if is_compressed:
            data = _decompress(f"json method={request.method} path={request.path}", stream.body)
            json_stream = BytesIO(data)
        else:
            json_stream = stream
        return super().parse(json_stream, media_type=stream.content_type, parser_context=parser_context)


class MultiPartCompressedJsonParser(MultiPartParser):
    def parse(self, stream, media_type=None, parser_context=None):
        request = parser_context["request"]
        files = super().parse(stream, media_type=media_type, parser_context=parser_context).files
        if len(files) != 1:
            _logger.warning(f"MultiPartCompressedJsonParser unexpected num of files: {len(files)}")
            raise ParseError(f"Only a single file is supported for this endpoint. files={len(files)}")
        json_file = next(files.values())
        if _is_compressed(request.headers):
            data = _decompress(f"mp_file method={request.method} path={request.path}", json_file.read())
        else:
            data = json_file.read()
        json_file.seek(0)
        request.build_stats_data_file = json_file
        return json.loads(data)


class BaseBuildSenseIngestionView(APIView):
    view_type = "app"
    audience = AccessTokenAudience.BUILDSENSE_API
    authentication_classes = (AuthenticationFromInternalHeaders,)
    permission_classes = (AccessTokensPermissions,)
    parser_classes = (MultiPartCompressedJsonParser, CompressedJsonParser)

    def dispatch(self, request, *args, **kwargs):
        self.repo_slug = kwargs.pop("repo_slug")
        self.customer_slug = kwargs.pop("customer_slug", None)
        return super().dispatch(request, *args, **kwargs)

    def handle_exception(self, exc):
        if isinstance(exc, BadDataError):
            _logger.warning(f"Bad data error ({self.request.method}): {exc}")
            error_info = {"error": {"message": str(exc)}}
            return Response(status=http.HttpResponseBadRequest.status_code, data=error_info)
        return super().handle_exception(exc)

    def initial(self, request, *args, **kwargs) -> None:
        super().initial(request, *args, **kwargs)
        if not isinstance(request.data, dict):
            raise BadDataError("Unexpected buildsense data (must be dict)")
        repo_claims: RepoClaims = request.auth
        repo = Repo.get_by_ids_and_user_or_404(
            customer_id=repo_claims.customer_pk, repo_id=repo_claims.repo_pk, user=request.user
        )
        if repo.slug != self.repo_slug:
            _logger.warning(
                f"repo slug mismatch {repo=} repo_slug_from_token={repo.slug} repo_slug_from_url={self.repo_slug} {repo_claims.token_id=} {repo_claims.username}="
            )
            raise PermissionDenied(f"Invalid repo slug: {self.repo_slug}")
        self.repo = repo
        # Initially for restricted token, we do more data validation in PantsDataIngestion,
        # Later we wll do that all the time (but for now, we do want the unhandled errors when there is a data issue)
        validate = request.auth.restricted
        # Silencing timeouts (from the scm integration api service) is ok because the data we may fail to get from this service
        # when the build is sumbitted via the API will be fetched during background processing (ProcessPantsRun) and will be used there.
        self.ingestor = PantsDataIngestion.for_repo(repo, validate=validate, silence_timeouts=True)


class BuildsenseConfig(BaseBuildSenseIngestionView):
    _CI_CAPTURE_CONFIG = {
        "CIRCLECI": r"^CIRCLE.*",
        "TRAVIS": r"^TRAVIS.*",
        "GITHUB_ACTIONS": r"^GITHUB.*",
        # Unlike other CI systems, BITBUCKET doesn't have a default env variable that
        # indicates the it is a bitbucket environment.
        # See: https://support.atlassian.com/bitbucket-cloud/docs/variables-and-secrets/
        "BITBUCKET_BUILD_NUMBER": r"^BITBUCKET.*",
        "BUILDKITE": r"^BUILDKITE.*",
    }
    # Plugin code depends on this schema!
    # Changes should be done with care!
    # See: toolchain/pants/buildsense/converter.py:WorkUnitCoverter.from_server
    # Due to a bug in implementeation, we try to read the ci_capture from the top level of the dict instead of from the "config" dict.
    # This workaround is here to prevent the plugin from crashing.
    # Once we fix & ship and made sure all of our customers have upgraded, we can get rid of this workaround.
    _CONFIG = {
        "ci_capture": _CI_CAPTURE_CONFIG,
        "config": {
            "work_units": {
                "artifacts": ["stdout", "stderr", "xml_results"],
                "metadata": [
                    "exit_code",
                    "definition",
                    "source",
                    "address",
                    "addresses",
                    "action_digest",
                    "environment_type",
                    "environment_name",
                ],
            },
            "ci_capture": _CI_CAPTURE_CONFIG,
        },
    }

    def options(self, request):
        return Response(self._CONFIG)


class BuildsenseIngestionView(BaseBuildSenseIngestionView):
    # Allows for user agents like: "pants/v2.9.0.dev3 toolchain/v0.16.0" and "pants/v2.9.0rc0+gita0a1a7d5 toolchain/v0.16.0"
    _USER_AGENT_EXPRESSION = re.compile(
        r"pants\/v(?P<pn>\d{1,4}\.\d{1,4}\.[\d\.a-z+]+) toolchain\/v(?P<tc>\d{1,4}\.\d{1,4}\.[\d\.a-z+])"
    )

    def _get_versions(self, request) -> tuple[str | None, str | None]:
        user_agent = request.headers.get("User-Agent", "")
        match = self._USER_AGENT_EXPRESSION.match(user_agent)
        if not match:
            # just log for now, later on we want to notify sentry since this is probably an early indicator that something downstream is wrong.
            _logger.warning(f"unexpected_user_agent: {user_agent=}")
            return None, None
        pants_version, toolchain_plugin_version = match.groups()
        return pants_version, toolchain_plugin_version

    def _get_request_context(self, request) -> RequestContext:
        """pants/v2.9.0.dev3 toolchain/v0.16.0."""
        pants_version, toolchain_plugin_version = self._get_versions(request)
        content_length_str = request.headers.get("Content-Length", "-1")
        if not content_length_str.isnumeric():
            _logger.warning(f"invalid content length header: {content_length_str=}")
            content_length = None
        else:
            content_length = int(content_length_str)
        return RequestContext(
            client_ip=get_client_ip(request),
            request_id=request.request_id,
            accept_time=utcnow(),
            stats_version=request.headers.get("X-Pants-Stats-Version", "2"),
            toolchain_plugin_version=toolchain_plugin_version,
            pants_version=pants_version,
            content_length=content_length,
        )

    def _get_build_link(self, request, run_id, repo) -> str:
        host = request.get_host()
        return f"{request.scheme}://{host}/organizations/{repo.customer.slug}/repos/{repo.slug}/builds/{run_id}/"

    def post(self, request, run_id: str):
        user = request.user
        if request.auth.impersonated_user_api_id:
            _logger.warning(
                f"impersonated_user_api_id passed to store_build_start. this is unexpected and will be ignored. {request.auth.impersonated_user_api_id}"
            )
        request_ctx = self._get_request_context(request)
        created, ci_user = self.ingestor.store_build_start(
            build_stats=request.data,
            user=user,
            request_ctx=request_ctx,
        )
        response_data = {
            "saved": created,
            "link": self._get_build_link(request, run_id, self.repo),
            "ci_user_api_id": ci_user.api_id if ci_user else None,
        }
        return Response(response_data, status=201 if created else 200)

    def patch(self, request, run_id: str):
        user = request.user
        # we use the actual auth user to get the repo to make sure that user has access to that repo even in impersonation scenarios
        impersonated_user = _get_impersonation_user(request.auth)
        request_ctx = self._get_request_context(request)
        created = self.ingestor.store_build_ended(
            build_stats=request.data,
            user=user,
            impersonated_user=impersonated_user,
            request_ctx=request_ctx,
            build_stats_compressed_file=getattr(request, "build_stats_data_file", None),
        )
        response_data = {"created": created, "link": self._get_build_link(request, run_id, self.repo)}
        return Response(data=response_data, status=201 if created else 200)


class WorkunitsIngestionView(BaseBuildSenseIngestionView):
    def post(self, request, run_id: str):
        user = request.user
        workunits = request.data.get("workunits")
        ci_user = _get_impersonation_user(request.auth)
        user_api_id = ci_user.api_id if ci_user else user.api_id
        updated = self.ingestor.ingest_work_units(
            run_id=run_id, user_api_id=user_api_id, accept_time=utcnow(), workunits_json=workunits
        )
        return Response("OK", status=201 if updated else 200)


class BuildsenseBatchIngestionView(BaseBuildSenseIngestionView):
    def post(self, request):
        user = request.user
        version = request.data.get("version")
        if not version:
            _logger.warning(f"Missing version data in request {request.data.keys()}")
            raise BadDataError("Missing version data")
        if version != "1":
            _logger.warning(f"invalid {version=}")
            raise BadDataError("Invalid version data")
        builds = request.data.get("build_stats")
        if not builds:
            _logger.warning(f"No builds provided {version=}. {request.data.keys()}")
            raise BadDataError("Invalid payload")

        build_user = _get_impersonation_user(request.auth) or user
        num_of_builds = len(builds)
        _logger.info(f"queue_batched_builds {version=} builds={num_of_builds} repo_slug={self.repo.slug}")
        self.ingestor.queue_batched_builds(
            batched_builds=builds,
            user_api_id=build_user.api_id,
            accepted_time=utcnow(),
            request_id=request.request_id,
            num_of_builds=num_of_builds,
        )
        return Response("OK", status=201)


class ArtifactsIngestionView(BaseBuildSenseIngestionView):
    parser_classes = (MultiPartParser,)  # type: ignore[assignment]
    _PANTS_LOG_ARTIFACT_NAME = "pants_run_log"  # See buildsense/state.py

    def post(self, request, run_id: str):
        user = request.user
        ci_user = _get_impersonation_user(request.auth)
        _logger.info(f"ingest_artifacts {ci_user=} {user=} {run_id=}")
        files = request.FILES
        pants_log = files.get(self._PANTS_LOG_ARTIFACT_NAME)
        if pants_log:
            self.ingestor.save_run_log(
                run_id=run_id,
                user_api_id=user.api_id,
                fp=pants_log,
            )
        if len(files) == 1 and pants_log:
            # Just the log, no other artifacts
            return Response("OK", status=201)
        descriptors_file = files.get("descriptors.json")
        if not descriptors_file:
            raise BadDataError("descriptors.json is missing from uploaded files")
        descriptors_json = _decompress("ingest_artifacts descriptors.json", descriptors_file.read())
        descriptors = json.loads(descriptors_json)  # TODO: handle bad json
        # TODO: see if there are keys in files not in descriptors
        for filename, descriptor in descriptors.items():
            artifact_file = files.get(filename)
            if not filename:
                # log error
                continue
            # TODO: validate data in descriptor
            self.ingestor.ingest_artifact(
                run_id=run_id,
                user_api_id=user.api_id,
                descriptor=descriptor,
                fp=artifact_file,
            )
        return Response("OK", status=201)
