# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from toolchain.aws.aws_api import AWSService
from toolchain.base.toolchain_error import ToolchainAssertion


class ElasticSearch(AWSService):
    service = "es"

    def _get_domain_names(self) -> list[str]:
        return [domain["DomainName"] for domain in self.client.list_domain_names()["DomainNames"]]

    def get_domain_endpoint(self, tags: dict[str, str]) -> str:
        es_domain = self._get_domain(tags)
        return es_domain["Endpoints"]["vpc"]

    def _get_domain(self, tags: dict[str, str]) -> dict:
        if not tags:
            raise ToolchainAssertion("Must specify tags.")
        names = self._get_domain_names()
        es_domains = self.client.describe_elasticsearch_domains(DomainNames=names)["DomainStatusList"]
        for es_domain in es_domains:
            raw_aws_tags = self.client.list_tags(ARN=es_domain["ARN"])["TagList"]
            if self.is_tag_subset(raw_aws_tags, tags):
                return es_domain
        raise ToolchainAssertion(f"ES Domain with tags {tags!r} not found.")
