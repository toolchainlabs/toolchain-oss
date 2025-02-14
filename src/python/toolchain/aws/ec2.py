# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import ipaddress
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from toolchain.aws.aws_api import AWSService
from toolchain.base.toolchain_error import ToolchainAssertion


@dataclass(frozen=True)
class Ec2Instance:
    instance_id: str
    private_dns_name: str  # Maps directly to k8s node name
    availability_zone: str

    @classmethod
    def from_boto(cls, instance_dict: dict) -> Ec2Instance:
        return cls(
            instance_id=instance_dict["InstanceId"],
            private_dns_name=instance_dict["PrivateDnsName"],
            availability_zone=instance_dict["Placement"]["AvailabilityZone"],
        )


@dataclass(frozen=True)
class Subnet:
    name: str | None
    subnet_id: str
    cidr: ipaddress.IPv4Network

    @classmethod
    def from_ec2_subnet(cls, subnet_json: dict) -> Subnet:
        tags = AWSService.tags_to_dict(subnet_json.get("Tags", []))
        cidr = ipaddress.IPv4Network(subnet_json["CidrBlock"], strict=True)
        name = tags.get("Name")  # Name tag is optional and not always there.
        return cls(name=name, subnet_id=subnet_json["SubnetId"], cidr=cidr)

    def get_address_component(self, index: int) -> int:
        return int(self.cidr.network_address.exploded.split(".")[index])


class EC2(AWSService):
    service = "ec2"

    def _iter_instances(self, instances_response) -> Iterator[dict]:
        for reservation in instances_response["Reservations"]:
            yield from reservation["Instances"]

    def get_instance_private_ip(self, instance_id: str) -> str | None:
        response = self.client.describe_instances(InstanceIds=[instance_id])
        for instance in self._iter_instances(response):
            if instance["InstanceId"] == instance_id:
                return instance["PrivateIpAddress"]
        return None

    def get_security_group_id_by_name(self, group_name: str) -> str | None:
        """Return boto3 SecurityGroup resources for the security group with the given name."""
        security_group_data = self.client.describe_security_groups(
            Filters=[{"Name": "group-name", "Values": [group_name]}]
        )["SecurityGroups"]
        if len(security_group_data) == 0:
            return None
        elif len(security_group_data) > 1:  # Should never happen, since AWS enforces name uniqueness.
            raise ToolchainAssertion(f"Found more than one security group with name {group_name}!")
        return security_group_data[0]["GroupId"]

    def get_instance_ids_by_tag(self, tag_name: str, tag_values: Sequence[str]) -> tuple[str, ...]:
        tag_filter = [{"Name": f"tag:{tag_name}", "Values": tag_values}]
        response = self.client.describe_instances(Filters=tag_filter)
        return tuple(instance["InstanceId"] for instance in self._iter_instances(response))

    def get_subnets(self) -> tuple[Subnet, ...]:
        subnets_json = self.client.describe_subnets()["Subnets"]
        return tuple(Subnet.from_ec2_subnet(sn) for sn in subnets_json)

    def get_instances(self, instance_ids: Sequence[str]) -> tuple[Ec2Instance, ...]:
        response = self.client.describe_instances(InstanceIds=list(instance_ids))
        return tuple(Ec2Instance.from_boto(instance) for instance in self._iter_instances(response))

    def terminate_instance(self, instance_id: str) -> None:
        self.client.terminate_instances(InstanceIds=[instance_id], DryRun=False)
