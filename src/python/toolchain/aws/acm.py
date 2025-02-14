# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from toolchain.aws.aws_api import AWSService


class ACM(AWSService):
    service = "acm"

    def get_cert_arn_for_domain(self, domain_name: str) -> str | None:
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/acm.html#ACM.Client.list_certificates
        response = self.client.list_certificates(CertificateStatuses=["ISSUED"])
        if "NextToken" in response:
            # not supporting pagination yet.
            raise NotImplementedError
        for cert in response["CertificateSummaryList"]:
            if cert["DomainName"] == domain_name:
                return cert["CertificateArn"]
        return None
