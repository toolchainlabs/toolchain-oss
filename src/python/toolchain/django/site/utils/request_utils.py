# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from io import BytesIO

from django.http.multipartparser import MultiPartParserError
from django.http.request import HttpRequest, QueryDict
from django.utils.datastructures import MultiValueDict


def get_client_ip(request) -> str | None:
    fwd_for_ip_address = request.META.get("HTTP_X_FORWARDED_FOR", "").strip().split(",")
    if not fwd_for_ip_address:
        return None
    return fwd_for_ip_address[0].strip()


def load_post_and_files(request: HttpRequest) -> None:
    """Based on https://github.com/django/django/blob/stable/4.1.x/django/http/request.p _load_post_and_files But parses
    files regradless of the request.method value."""
    if request.method not in ("POST", "PATCH"):
        request._post, request._files = (
            QueryDict(encoding=request._encoding),
            MultiValueDict(),
        )
        return
    if request._read_started and not hasattr(request, "_body"):
        request._mark_post_parse_error()
        return

    if request.content_type == "multipart/form-data":
        if hasattr(request, "_body"):
            # Use already read data
            data = BytesIO(request._body)
        else:
            data = request
        try:
            request._post, request._files = request.parse_file_upload(request.META, data)
        except MultiPartParserError:
            # An error occurred while parsing POST data. Since when
            # formatting the error the request handler might access
            # self.POST, set self._post and self._file to prevent
            # attempts to parse POST data again.
            request._mark_post_parse_error()
            raise
    elif request.content_type == "application/x-www-form-urlencoded":
        request._post, request._files = (
            QueryDict(request.body, encoding=request._encoding),
            MultiValueDict(),
        )
    else:
        request._post, request._files = (
            QueryDict(encoding=request._encoding),
            MultiValueDict(),
        )
