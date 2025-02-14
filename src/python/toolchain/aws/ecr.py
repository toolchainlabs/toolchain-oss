# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import base64
from dataclasses import dataclass

from toolchain.aws.aws_api import AWSService


@dataclass(frozen=True)
class DockerAuth:
    username: str
    password: str
    registry: str

    def to_auth_dict(self) -> dict[str, str]:
        return {"ServerAddress": self.registry, "Username": self.username, "Password": self.password}


class ECR(AWSService):
    service = "ecr"

    def ensure_repository(self, name: str) -> bool:
        try:
            self.client.create_repository(repositoryName=name)
            return True
        except self.client.exceptions.RepositoryAlreadyExistsException:
            return False

    def get_auth_data(self) -> DockerAuth:
        auth_data = self.client.get_authorization_token()["authorizationData"][0]
        username, password = base64.b64decode(auth_data["authorizationToken"]).decode().split(":")
        return DockerAuth(username=username, password=password, registry=auth_data["proxyEndpoint"])
