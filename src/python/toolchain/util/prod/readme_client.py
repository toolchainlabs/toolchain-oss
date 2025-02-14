# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from toolchain.aws.secretsmanager import SecretsManager
from toolchain.base.toolchain_error import ToolchainAssertion


@dataclass(frozen=True)
class ReadmePage:
    slug: str
    title: str
    body: str
    category: str


class ReadmeClient:
    _BASE_URL = "https://dash.readme.com/api/v1/"

    @classmethod
    def from_aws_secret(cls, aws_region: str) -> ReadmeClient:
        secrets_mgr = SecretsManager(region=aws_region)
        api_key_secret = secrets_mgr.get_secret("readme-api-key")
        if not api_key_secret:
            raise ToolchainAssertion("Failed to load Readme.com API Key")
        api_key = json.loads(api_key_secret)["README_COM_API_KEY"]
        return cls(api_key=api_key)

    def __init__(self, api_key: str) -> None:
        self._client = httpx.Client(
            base_url=self._BASE_URL,
            headers={
                "Authorization": f"Basic {api_key}",
                "Accept": "application/json",
                "User-Agent": "Toolchain-Integration",
            },
        )

    def _get(self, path: str, allow_404: bool = False) -> dict | None:
        response = self._client.get(path)
        if allow_404 and response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def ping(self) -> None:
        # https://docs.readme.com/reference/introduction
        self._get("")

    def _post(self, path: str, payload: dict) -> dict | None:
        response = self._client.post(path, json=payload)
        response.raise_for_status()
        return response.json()

    def _put(self, path: str, payload: dict) -> dict | None:
        response = self._client.put(path, json=payload)
        response.raise_for_status()
        return response.json()

    def get_category_id(self, slug: str) -> str:
        # https://docs.readme.com/reference/getcategories
        categories = self._get("categories")
        return next(cat["_id"] for cat in categories if cat["slug"] == slug)  # type: ignore[union-attr]

    def get_doc(self, slug) -> dict | None:
        # https://docs.readme.com/reference/getdoc
        return self._get(f"docs/{slug}", allow_404=True)

    def create_doc(self, *, page: ReadmePage, category_id: str) -> bool:
        # https://docs.readme.com/reference/createdoc
        payload = {
            "hidden": True,
            "order": 10,
            "title": page.title,
            "type": "basic",
            "body": page.body,
            "category": category_id,
        }
        self._post("docs", payload)
        return True

    def update_doc(self, *, page: ReadmePage, category_id: str, doc: dict) -> bool:
        # https://docs.readme.com/reference/updatedoc
        if doc["category"] != category_id:
            raise ToolchainAssertion(f"Category id mismatch. got: {doc['category']} expected: {category_id}")
        payload = {
            "hidden": doc["hidden"],
            "order": doc["order"],
            "title": page.title,
            "type": doc["type"],
            "body": page.body,
            "category": category_id,
        }
        self._put(f"docs/{page.slug}", payload)
        return True

    def create_or_update_doc(self, page: ReadmePage) -> str:
        category_id = self.get_category_id(page.category)
        doc = self.get_doc(page.slug)
        if not doc:
            self.create_doc(page=page, category_id=category_id)
            return "created"
        self.update_doc(page=page, category_id=category_id, doc=doc)
        return "updated"
