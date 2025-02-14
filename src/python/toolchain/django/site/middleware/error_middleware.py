# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging

from django.db.utils import OperationalError
from django.http.response import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from toolchain.aws.errors import is_transient_aws_error
from toolchain.base.toolchain_error import ToolchainTransientError

_logger = logging.getLogger(__name__)


class TransientErrorsMiddleware(MiddlewareMixin):
    _TRANSIENT_EXCEPTIONS_TYPES = (OperationalError, ToolchainTransientError)

    def process_exception(self, request, exception):
        if isinstance(exception, self._TRANSIENT_EXCEPTIONS_TYPES) or is_transient_aws_error(exception):
            # 503 - Service Unavailable
            error_type = type(exception).__name__
            _logger.warning(f"transient_error {error_type=} path={request.path} {exception!r}")
            return JsonResponse(data={"error": "transient", "error_type": error_type}, status=503)
        return None
