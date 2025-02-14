# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
from dataclasses import dataclass

from toolchain.aws.aws_api import AWSService
from toolchain.base.toolchain_error import ToolchainAssertion


@dataclass(frozen=True)
class Distribution:
    dist_id: str
    status: str
    domain: str
    last_modified: datetime.datetime


class Cloudfront(AWSService):
    service = "cloudfront"

    def get_distribution_for_tags(self, tags: dict[str, str]) -> Distribution:
        dist_list = self.client.list_distributions()["DistributionList"]
        if dist_list.get("NextMarker"):
            raise ToolchainAssertion("get_distribution_for_tags pagination is not implemented.")
        dist = self._match_dists(dist_list, tags)
        if not dist:
            raise ToolchainAssertion(f"Distribution with {tags} not found.")
        aliases = dist["Aliases"]
        domain = aliases["Items"][0] if aliases["Quantity"] > 0 else dist["DomainName"]
        return Distribution(
            dist_id=dist["Id"], status=dist["Status"], domain=domain, last_modified=dist["LastModifiedTime"]
        )

    def _match_dists(self, dist_list: dict, tags: dict[str, str]) -> dict | None:
        for dist in dist_list["Items"]:
            if not dist["Enabled"]:
                continue
            tags_response = self.client.list_tags_for_resource(Resource=dist["ARN"])
            if self.is_tag_subset(tags_response["Tags"]["Items"], tags):
                return dist
        return None
