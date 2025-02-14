# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from dataclasses import dataclass

from toolchain.aws.aws_api import AWSService
from toolchain.base.toolchain_error import ToolchainAssertion


@dataclass
class AutoscalingInstance:
    instance_id: str
    launch_config: str | None
    lifecycle_state: str

    @classmethod
    def from_boto(cls, boto_instance: dict):
        return cls(
            boto_instance["InstanceId"], boto_instance.get("LaunchConfigurationName"), boto_instance["LifecycleState"]
        )


AutoScalingInstances = tuple[AutoscalingInstance, ...]


@dataclass(frozen=True)
class AutoscalingGroup:
    name: str
    min_size: int
    max_size: int
    desired_capacity: int
    launch_config: str
    instances: AutoScalingInstances
    termination_policies: tuple[str, ...]

    @classmethod
    def from_boto(cls, name: str, boto_asg: dict) -> AutoscalingGroup:
        instances = tuple(AutoscalingInstance.from_boto(inst) for inst in boto_asg.get("Instances", tuple()))
        return cls(
            name,
            boto_asg["MinSize"],
            boto_asg["MaxSize"],
            boto_asg["DesiredCapacity"],
            boto_asg["LaunchConfigurationName"],
            instances,
            tuple(boto_asg["TerminationPolicies"]),
        )


class Autoscaling(AWSService):
    service = "autoscaling"

    def get_auto_scaling_group(self, name: str) -> AutoscalingGroup:
        """Get info about an auto-scaling group.

        :param str name: Name of the auto-scaling group.
        :rtype: :class:`AutoscalingGroup`
        """
        response = self.client.describe_auto_scaling_groups(AutoScalingGroupNames=[name])
        asgs = response.get("AutoScalingGroups")
        if len(asgs) != 1:
            raise ToolchainAssertion(f"Expected one AutoScalingGroup in response but found {len(asgs)}")
        asg = asgs[0]
        # Note that if the older launch config was deleted then stale instances will have no
        # LaunchConfigurationName in the response, so we let it be None. We only care about
        # whether it's equal to the current launch config or not anyway.
        return AutoscalingGroup.from_boto(name, asg)

    def update_desired_capacity(self, name: str, capacity: int) -> None:
        self.client.set_desired_capacity(AutoScalingGroupName=name, DesiredCapacity=capacity, HonorCooldown=False)

    def get_resources_with_tag(self, tag_key: str) -> tuple[str, ...]:
        resp = self.client.describe_tags(Filters=[{"Name": "key", "Values": [tag_key]}])
        if resp.get("NextToken"):
            raise NotImplementedError("Pagination not implemented on get_resources_with_tag()")
        return tuple(tag["ResourceId"] for tag in resp["Tags"])

    def terminate_and_decrement(self, instance_id: str) -> None:
        """Terminates the specified instance and adjusts the desired group size (decrements it by 1)"""
        self.client.terminate_instance_in_auto_scaling_group(
            InstanceId=instance_id, ShouldDecrementDesiredCapacity=True
        )
