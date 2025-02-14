# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from toolchain.aws.aws_api import AWSService


class ECS(AWSService):
    service = "ecs"

    def register_task_definition(self, task_definition_json: dict) -> str:
        resp = self.client.register_task_definition(**task_definition_json)
        return resp["taskDefinition"]["taskDefinitionArn"]

    def create_fargate_service(
        self, cluster_name: str, replicas_count: int, name: str, task_name: str, network_cfg: dict
    ) -> None:
        self.client.create_service(
            cluster=cluster_name,
            desiredCount=replicas_count,
            serviceName=name,
            launchType="FARGATE",
            propagateTags="TASK_DEFINITION",
            networkConfiguration=network_cfg,
            taskDefinition=task_name,
            enableECSManagedTags=True,
            enableExecuteCommand=True,
        )

    def is_service_exists(self, cluster_name: str, service_name: str) -> bool:
        response = self.client.describe_services(cluster=cluster_name, services=[service_name])
        return len(response["services"]) != 0

    def update_fargate_service(self, cluster_name: str, replicas_count: int, name: str, task_name: str) -> None:
        self.client.update_service(
            cluster=cluster_name,
            service=name,
            desiredCount=replicas_count,
            taskDefinition=task_name,
            forceNewDeployment=True,
            enableECSManagedTags=True,
            enableExecuteCommand=True,
        )
