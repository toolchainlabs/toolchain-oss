# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.aws.aws_api import AWSService
from toolchain.base.toolchain_error import ToolchainAssertion


class ELB(AWSService):
    service = "elbv2"

    def _check_pagination(self, resp, api):
        # Pagination is not implemented in our code, mostly because we don't have a lot of resources
        # so it doesn't make a lot of sense to implement it.
        # However, if we ever hit a number resources (ELBs, listeners) that requires the AWS API to
        # paginate, this code is designed to blow up instead of silently failing or returning invalid results
        if resp.get("NextMarker"):
            raise NotImplementedError(f"Pagination not implemented on {api}()")

    def get_elb_with_cert(self, cert_arn):
        response = self.client.describe_load_balancers()
        self._check_pagination(response, "describe_load_balancers")
        for elb in response["LoadBalancers"]:
            listeners_resp = self.client.describe_listeners(LoadBalancerArn=elb["LoadBalancerArn"])
            self._check_pagination(listeners_resp, "get_elb_with_cert")
            for listener in listeners_resp["Listeners"]:
                for certificate in listener.get("Certificates", []):
                    if certificate["CertificateArn"] == cert_arn:
                        return elb
        return None

    def get_security_group_for_cert(self, cert_arn):
        elb = self.get_elb_with_cert(cert_arn)
        if not elb:
            raise ToolchainAssertion(f"No ELB associated with cert: {cert_arn}")
        security_groups = elb["SecurityGroups"]
        if len(security_groups) != 1:
            elb_name = elb["LoadBalancerName"]
            raise ToolchainAssertion(
                f"Unexpected number of security groups associated with {elb_name}. {security_groups}"
            )
        return security_groups[0]
