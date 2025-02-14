# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from urllib.parse import parse_qs, urlparse

from rest_framework.pagination import CursorPagination


class ToolchainCursorPagination(CursorPagination):
    ordering = "id"
    page_size_query_param = "page_size"

    def _get_cursor(self, link):
        # Parsed query values are returned as lists, so some hackery is in order to get us only the cursor.
        return parse_qs(urlparse(link).query).get("cursor", [None])[0]

    def get_previous_link(self):
        link = super().get_previous_link()
        return self._get_cursor(link)

    def get_next_link(self):
        link = super().get_next_link()
        return self._get_cursor(link)


class ToolchainSlugCursorPagination(ToolchainCursorPagination):
    ordering = "slug"
