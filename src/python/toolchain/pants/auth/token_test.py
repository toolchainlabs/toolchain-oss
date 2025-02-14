# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

from toolchain.pants.auth.token import AuthToken


class TestAuthToken:
    TOKEN_TEMPLATE = "eyJhbGciOiJIUzI1NiIsImtpZCI6InRzOjE1NzYxMTM5NTkiLCJ0eXAiOiJKV1QifQ.{0}.WMxdTjpaSnwkSkdTxppIB0Y6ynAzm61icnxXrEmOCrY"
    CLAIMS_NEEDS_PADDING = "eyJleHAiOjE2MzgxMzIzMjUsImlhdCI6MTYyMjU4MDMyNSwiamlkIjoiQlB0OGJ5TVoyY0E3cUozeWo4cGdiaSIsImF1ZCI6WyJidWlsZHNlbnNlIiwiY2FjaGVfcm8iLCJjYWNoZV9ydyIsImltcGVyc29uYXRlIl0sInVzZXJuYW1lIjoiYXNoZXIiLCJ0eXBlIjoicmVmcmVzaCIsInRvb2xjaGFpbl91c2VyIjoiZlE2QU5xdTJzOUd3QXZIQ0p6amNnQSIsInRvb2xjaGFpbl9yZXBvIjoiSzJhRExGQXpmOUxFN29LZ01weHhCQSIsInRvb2xjaGFpbl9jdXN0b21lciI6ImhkdDJobmlVWGVtc2FIRHVpQmFwNEIiLCJpc3MiOiJ0b29sY2hhaW4iLCJ0b29sY2hhaW5fY2xhaW1zX3ZlciI6Mn0"
    CLAIMS_NO_PADDING_NEEDED = "eyJleHAiOjE2MzE5OTk4NzcsImlhdCI6MTYxNjQ0Nzg3NywiamlkIjoibzdMZHY4aWREaHZBWFVNdFlyYWZYZCIsImF1ZCI6WyJidWlsZHNlbnNlIiwiY2FjaGVfcm8iLCJjYWNoZV9ydyIsImltcGVyc29uYXRlIl0sInVzZXJuYW1lIjoiYXNoZXJmIiwidHlwZSI6InJlZnJlc2giLCJ0b29sY2hhaW5fdXNlciI6ImRSQ3pFM3dWS3pHc1JKaW5ZNm5ZNloiLCJ0b29sY2hhaW5fcmVwbyI6IkU3WUJ4R0JxN0V1N2Fma2hwaWJZNGYiLCJ0b29sY2hhaW5fY3VzdG9tZXIiOiJleEJnY2lHS2s3aHl6R1ZRN01Ec1RuIiwiaXNzIjoidG9vbGNoYWluIiwidG9vbGNoYWluX2NsYWltc192ZXIiOjJ9"

    def test_load_token_from_string_padding_needed(self) -> None:
        token_str = self.TOKEN_TEMPLATE.format(self.CLAIMS_NEEDS_PADDING)
        token = AuthToken.from_access_token_string(token_str)
        assert token.expires_at == datetime.datetime(2021, 11, 28, 20, 45, 25, tzinfo=datetime.timezone.utc)
        assert token.repo_id is None
        assert token.customer_id is None
        assert token.user == "fQ6ANqu2s9GwAvHCJzjcgA"
        assert token.repo == "K2aDLFAzf9LE7oKgMpxxBA"

    def test_load_token_from_string_no_padding_needed(self) -> None:
        token_str = self.TOKEN_TEMPLATE.format(self.CLAIMS_NO_PADDING_NEEDED)
        token = AuthToken.from_access_token_string(token_str)
        assert token.expires_at == datetime.datetime(2021, 9, 18, 21, 17, 57, tzinfo=datetime.timezone.utc)
        assert token.repo_id is None
        assert token.customer_id is None
        assert token.user == "dRCzE3wVKzGsRJinY6nY6Z"
        assert token.repo == "E7YBxGBq7Eu7afkhpibY4f"
