# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime
import re
from dataclasses import Field, asdict, dataclass, fields
from enum import Enum, unique
from typing import Dict, List, Optional, Union

from toolchain.base.toolchain_error import ToolchainError


class InvalidRunInfoData(ToolchainError):
    """Error is raised when there is unexpected data in run info or when there is an issue parsing RunInfo data."""


@unique
class ScmProvider(Enum):
    GITHUB = "github"
    BITBUCKET = "bitbucket"


def _convert_timestamps(json_dict: dict, *fields: str):
    """Converts specified fields from float() timestamps to datetime objects."""
    for field in fields:
        if field not in json_dict:
            continue
        ts = json_dict.pop(field)
        json_dict[field] = datetime.datetime.fromtimestamp(float(ts), datetime.timezone.utc)


@dataclass
class ServerInfo:
    accept_time: datetime.datetime
    environment: str
    request_id: str
    stats_version: str
    s3_bucket: str
    s3_key: str
    client_ip: Optional[str] = None

    @classmethod
    def from_json_dict(cls, json_dict: dict):
        json_dict = dict(json_dict)  # don't modify the param passed down
        _convert_timestamps(json_dict, "accept_time")
        return cls(**json_dict)

    def to_json_dict(self) -> dict:
        json_dict = asdict(self)
        json_dict["accept_time"] = self.accept_time.timestamp()
        return json_dict


@dataclass
class WorkUnit:
    workunit_id: str
    name: str
    state: str
    version: int
    start: datetime.datetime
    last_update: datetime.datetime

    parent_id: Optional[str] = None
    end: Optional[datetime.datetime] = None

    @classmethod
    def from_json_dict(cls, json_dict: dict):
        json_dict = dict(json_dict)  # don't modify the param passed down
        _convert_timestamps(json_dict, "start", "end", "last_update")
        return cls(**json_dict)

    @classmethod
    def from_json_dicts(cls, work_unit_dicts: List[dict]):
        return [cls.from_json_dict(wu) for wu in work_unit_dicts]

    def to_json_dict(self) -> dict:
        json_dict = asdict(self)
        for field in ["start", "end", "last_update"]:
            value = json_dict.pop(field)
            if value:
                json_dict[field] = int(value.timestamp())
        return json_dict


@unique
class RunType(Enum):
    PULL_REQUEST = "pull_request"
    BRANCH = "branch"
    TAG = "tag"


@unique
class CISystem(Enum):
    UNKNOWN = "unknown"
    TRAVIS = "travis"
    CIRCLE_CI = "circleci"
    GITHUB_ACTIONS = "github"
    BITBUCKET_PIPELINES = "bitbucket"
    BUILDKITE = "buildkite"

    @property
    def is_known(self) -> bool:
        return self != self.UNKNOWN


_CI_SYSTEMS_LINK_PATTERNS = {
    CISystem.TRAVIS: re.compile(r"^https://travis-ci\.com/"),
    CISystem.CIRCLE_CI: re.compile(r"^https://circleci\.com/"),
    CISystem.GITHUB_ACTIONS: re.compile(r"^https://github\.com/"),
    CISystem.BITBUCKET_PIPELINES: re.compile(r"^https://bitbucket\.org/"),
    CISystem.BUILDKITE: re.compile(r"^https://buildkite\.com/"),
}


@dataclass
class CIDetails:
    Type = RunType

    username: str
    run_type: RunType
    pull_request: Optional[int]
    job_name: Optional[str]
    build_num: int
    build_url: Optional[str]
    link: Optional[str] = None  # link to PR/commit in github/bitbucket
    ref_name: Optional[str] = None  # branch or git tag name

    @classmethod
    def from_json_dict(cls, json_dict: dict):
        json_dict = dict(json_dict)  # don't modify the param passed down
        pr_number = json_dict["pull_request"]
        json_dict.update(
            run_type=RunType(json_dict["run_type"]),
            # DynamoDB returns pr_number as float
            pull_request=int(pr_number) if pr_number else None,
        )
        return cls(**json_dict)

    def to_json_dict(self) -> dict:
        json_dict = asdict(self)
        json_dict["run_type"] = self.run_type.value
        return json_dict

    @property
    def ci_system(self) -> CISystem:
        if not self.build_url:
            return CISystem.UNKNOWN
        # Temporary/hacky way to infer CI System from build_url
        for ci, exp in _CI_SYSTEMS_LINK_PATTERNS.items():
            if exp.match(self.build_url):
                return ci
        return CISystem.UNKNOWN


@dataclass(frozen=True)
class RunKey:
    user_api_id: str
    repo_id: str
    run_id: str


@dataclass
class RunInfo:
    _DEPRECATED_FIELDS = ("report_url", "default_report")
    repo_id: str
    buildroot: str
    timestamp: datetime.datetime
    machine: str
    version: str
    path: str
    outcome: str
    cmd_line: str
    run_id: str  # json: id
    user_api_id: str
    customer_id: str
    server_info: ServerInfo
    computed_goals: List[str]
    specs_from_command_line: List[str]

    # Optional: calculated asynchronously
    run_time: Optional[datetime.timedelta]

    # optional (None/empty values are allowed)
    branch: Optional[str] = None
    revision: Optional[str] = None
    title: Optional[str] = None
    ci_info: Optional[CIDetails] = None
    indicators: Optional[dict] = None
    modified_fields: Optional[
        List[str]
    ] = None  # list of fields modified/change on the server before saving to dyanmodb.
    collected_platform_info: bool = False

    @classmethod
    def get_fields(cls) -> dict:
        run_info_fields: Dict[str, Union[Field, dict]] = {field.name: field for field in fields(cls)}
        run_info_fields.update(
            server_info={field.name: field for field in fields(ServerInfo)},
            ci_info={field.name: field for field in fields(CIDetails)},
        )
        del run_info_fields["indicators"]
        del run_info_fields["modified_fields"]
        del run_info_fields["collected_platform_info"]
        return run_info_fields

    @classmethod
    def _remove_deprecated(cls, json_dict: dict) -> None:
        for field_name in cls._DEPRECATED_FIELDS:
            json_dict.pop(field_name, None)

    @classmethod
    def from_json_dict(cls, json_dict: dict):
        json_dict = dict(json_dict)
        cls._remove_deprecated(json_dict)
        if isinstance(json_dict["server_info"], dict):
            json_dict["server_info"] = ServerInfo.from_json_dict(json_dict["server_info"])
        if isinstance(json_dict.get("ci_info"), dict):
            json_dict["ci_info"] = CIDetails.from_json_dict(json_dict["ci_info"])
        _convert_timestamps(json_dict, "timestamp")
        run_time = json_dict.get("run_time")
        json_dict["run_time"] = datetime.timedelta(milliseconds=run_time) if run_time else None
        cls._list_or_empty(json_dict, "computed_goals", "specs_from_command_line")
        return cls(**json_dict)

    @classmethod
    def _list_or_empty(cls, json_dict: dict, *fields: str) -> None:
        for field in fields:
            val = json_dict.get(field) or []
            json_dict[field] = val

    @property
    def has_trace(self) -> bool:
        return self.server_info.stats_version == "3" and self.outcome in {"SUCCESS", "FAILURE"}

    def to_json_dict(self) -> dict:
        json_dict = asdict(self)
        run_time = json_dict["run_time"]
        if run_time is not None:
            json_dict["run_time"] = int(run_time.total_seconds() * 1000)
        json_dict["timestamp"] = json_dict.pop("timestamp").timestamp()
        json_dict["server_info"] = self.server_info.to_json_dict()
        if self.ci_info:
            json_dict["ci_info"] = self.ci_info.to_json_dict()
        return json_dict
