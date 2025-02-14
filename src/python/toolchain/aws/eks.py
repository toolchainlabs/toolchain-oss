# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import re
from dataclasses import dataclass

from toolchain.aws.aws_api import AWSService


@dataclass(frozen=True)
class ClusterOIDCInfo:
    issuer_url: str
    issuer_id: str
    provider_uri: str
    provider_arn: str


class EKS(AWSService):
    service = "eks"
    ISSUER_ID_EXP = re.compile(r"[A-F0-9]{32}$")
    REGION_EXP = re.compile(r"oidc\.eks\.(?P<region>[a-z1-9-]{5,})\.amazonaws.com")

    def get_cluster_vpc_id(self, cluster_name: str) -> str:
        response = self.client.describe_cluster(name=cluster_name)
        return response["cluster"]["resourcesVpcConfig"]["vpcId"]

    def get_cluster_oidc_info(self, cluster_name: str) -> ClusterOIDCInfo:
        response = self.client.describe_cluster(name=cluster_name)
        issuer_url = response["cluster"]["identity"]["oidc"]["issuer"]
        aws_region = self.REGION_EXP.search(issuer_url).groupdict()["region"]  # type: ignore[union-attr]
        issuer_id = self.ISSUER_ID_EXP.search(issuer_url).group()  # type: ignore[union-attr]
        provider_uri = f"oidc.eks.{aws_region}.amazonaws.com/id/{issuer_id}"
        provider_arn = f"arn:aws:iam::{self.account_id}:oidc-provider/{provider_uri}"
        return ClusterOIDCInfo(
            issuer_url=issuer_url,
            issuer_id=issuer_id,
            provider_uri=provider_uri,
            provider_arn=provider_arn,
        )
