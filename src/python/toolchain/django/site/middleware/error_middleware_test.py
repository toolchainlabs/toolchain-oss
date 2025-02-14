# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json

import pytest
from botocore.exceptions import CredentialRetrievalError
from django.db.utils import OperationalError
from django.test import RequestFactory

from toolchain.base.toolchain_error import ToolchainAssertion, ToolchainTransientError
from toolchain.django.site.middleware.error_middleware import TransientErrorsMiddleware


@pytest.mark.django_db()
class TestTransientErrors:
    @pytest.fixture()
    def middleware(self) -> TransientErrorsMiddleware:
        return TransientErrorsMiddleware(get_response=lambda request: None)

    def _get_json(self, response) -> dict:
        assert response["Content-Type"] == "application/json"
        return json.loads(response.content)

    def test_process_exception_response_db_error(self, rf: RequestFactory, middleware) -> None:
        request = rf.get("/some/path")
        response = middleware.process_exception(request, OperationalError())
        assert response.status_code == 503
        assert self._get_json(response) == {"error": "transient", "error_type": "OperationalError"}

    def test_process_exception_response_aws_error(self, rf: RequestFactory, middleware) -> None:
        request = rf.get("/some/path")
        response = middleware.process_exception(
            request,
            CredentialRetrievalError(provider="jerry", error_msg="Error when retrieving credentials from iam-role"),
        )
        assert response.status_code == 503
        assert self._get_json(response) == {"error": "transient", "error_type": "CredentialRetrievalError"}

    def test_process_exception_response_toolchain_transient_error(self, rf: RequestFactory, middleware) -> None:
        request = rf.get("/some/path")
        response = middleware.process_exception(
            request,
            ToolchainTransientError("Maybe the dingo ate your baby!"),
        )
        assert response.status_code == 503
        assert self._get_json(response) == {"error": "transient", "error_type": "ToolchainTransientError"}

    def test_process_exception_pass(self, rf: RequestFactory, middleware) -> None:
        request = rf.get("/some/path")
        assert middleware.process_exception(request, ToolchainAssertion()) is None
