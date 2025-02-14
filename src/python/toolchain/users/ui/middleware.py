# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.shortcuts import redirect
from social_core.exceptions import SocialAuthBaseException
from social_core.utils import social_logger
from social_django.middleware import SocialAuthExceptionMiddleware


class ToolchainAuthExceptionMiddleware(SocialAuthExceptionMiddleware):
    """Based on https://github.com/python-social-auth/social-app-django/blob/master/social_django/middleware.py Modified
    to remove irrelevant code (using django.contrib.messages) and reduce logging level from error to warning so when we
    deny users access, it won't generate a sentry error."""

    def process_exception(self, request, exception):
        strategy = getattr(request, "social_strategy", None)
        if strategy is None or self.raise_exception(request, exception):
            return None
        if not isinstance(exception, SocialAuthBaseException):
            return None
        message = self.get_message(request, exception)
        url = self.get_redirect_uri(request, exception)
        social_logger.warning(message)
        return redirect(url) if url else None
