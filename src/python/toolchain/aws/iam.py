# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import logging
from dataclasses import dataclass

from toolchain.aws.aws_api import AWSService

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IAMUser:
    name: str
    tags: dict
    key_date: datetime.datetime
    key_id: str


@dataclass(frozen=True)
class IAMAccessKey:
    user_name: str
    access_key_id: str
    secret_access_key: str


class IAM(AWSService):
    service = "iam"

    def _check_pagination(self, response, api):
        if response.get("Marker"):
            raise NotImplementedError(f"Pagination not implemented on {api}()")

    def create_access_key(self, user_name: str) -> IAMAccessKey:
        response = self.client.create_access_key(UserName=user_name)
        fields = response["AccessKey"]
        return IAMAccessKey(
            user_name=fields["UserName"],
            access_key_id=fields["AccessKeyId"],
            secret_access_key=fields["SecretAccessKey"],
        )

    def deactivate_access_key(self, user_name: str, access_key_id: str) -> None:
        self.client.update_access_key(UserName=user_name, AccessKeyId=access_key_id, Status="Inactive")

    def delete_access_key(self, user: IAMUser):
        _logger.info(f"Delete access key for user={user.name} key_id={user.key_id}")
        self.client.delete_access_key(UserName=user.name, AccessKeyId=user.key_id)

    def get_current_user_name(self) -> str:
        """Return the name of the currently authorized user."""
        response = self.client.get_user()
        return response["User"]["UserName"]

    def get_users_with_old_keys(self, created_before: datetime.datetime) -> list[IAMUser]:
        users = []
        response = self.client.list_users()
        self._check_pagination(response, "list_users")
        for user in response["Users"]:
            username = user["UserName"]
            has_old_keys, key = self.has_old_keys(username, created_before)
            if not has_old_keys:
                continue
            tags = self.client.list_user_tags(UserName=username)["Tags"]
            users.append(
                IAMUser(
                    name=username, tags=self.tags_to_dict(tags), key_id=key["AccessKeyId"], key_date=key["CreateDate"]
                )
            )
        return users

    def delete_inactive_keys(self, username: str) -> int:
        count = 0
        response = self.client.list_access_keys(UserName=username)
        self._check_pagination(response, "list_access_keys")
        for key in response["AccessKeyMetadata"]:
            if key["Status"] != "Inactive":
                continue
            _logger.info(f"Deleting non-active access key with ID {key['AccessKeyId']} in status '{key['Status']}'")
            self.client.delete_access_key(UserName=username, AccessKeyId=key["AccessKeyId"])
            count += 1
        return count

    def has_old_keys(self, username: str, created_before: datetime.datetime):
        response = self.client.list_access_keys(UserName=username)
        self._check_pagination(response, "list_access_keys")
        for key in response["AccessKeyMetadata"]:
            if key["Status"] != "Active":
                continue
            if key["CreateDate"] <= created_before:
                return True, key
        return False, None

    def ensure_role(self, role_name: str, assume_role_policy: dict) -> bool:
        assume_role_policy_doc = json.dumps(assume_role_policy)
        try:
            self.client.create_role(RoleName=role_name, AssumeRolePolicyDocument=assume_role_policy_doc)
            return True
        except self.client.exceptions.EntityAlreadyExistsException:
            self.client.update_assume_role_policy(RoleName=role_name, PolicyDocument=assume_role_policy_doc)
            return False

    def create_role_with_policy(
        self,
        *,
        role_name: str,
        assume_role_policy: dict,
        inline_policy_name: str | None = None,
        inline_policy: dict | None = None,
        managed_policies: tuple[str, ...] = (),
    ) -> str:
        # TODO: check if role already exists
        resp = self.client.create_role(RoleName=role_name, AssumeRolePolicyDocument=json.dumps(assume_role_policy))
        for managed_policy in managed_policies:
            self.client.attach_role_policy(RoleName=role_name, PolicyArn=managed_policy)
        if inline_policy_name and inline_policy:
            self.client.put_role_policy(
                RoleName=role_name, PolicyName=inline_policy_name, PolicyDocument=json.dumps(inline_policy)
            )
        return resp["Role"]["Arn"]
